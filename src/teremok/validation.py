"""Documented Bot API rules, enforced the way real Telegram enforces them.

Every rule here cites the Bot API docs (see docs/validation.md). Violations
raise ApiRuleViolation; MockedSession converts them into genuine
TelegramBadRequest via the same check_response route as real error responses.
"""

from __future__ import annotations

import re
from typing import Any

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import InlineKeyboardMarkup

MAX_TEXT = 4096  # sendMessage: "1-4096 characters after entities parsing"
MAX_CAPTION = 1024  # sendPhoto etc.: "0-1024 characters after entities parsing"
MAX_CALLBACK_ANSWER = 200  # answerCallbackQuery: "0-200 characters"


class ApiRuleViolation(Exception):
    """A documented Bot API rule was violated by an outgoing method."""

    def __init__(self, description: str) -> None:
        self.description = description
        super().__init__(description)


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _resolve_parse_mode(bot: Bot, value: Any) -> str | None:
    if isinstance(value, Default):
        resolved = getattr(bot.default, value.name, None)
        return resolved if isinstance(resolved, str) else None
    return value if isinstance(value, str) else None


_TAG_TOKEN = re.compile(
    r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)"
    r"((?:\s+[a-zA-Z-]+(?:=(?:\"[^\"]*\"|'[^']*'))?)*)"
    r"\s*>"
)
_ATTR = re.compile(r"([a-zA-Z-]+)(?:=(?:\"([^\"]*)\"|'([^']*)'))?")
_CHAR_REF = re.compile(r"&(?:lt|gt|amp|quot|#[0-9]{1,7}|#x[0-9a-fA-F]{1,6});")

# Bot API "HTML style": tag -> allowed attributes
_HTML_ALLOWED: dict[str, frozenset[str]] = {
    "b": frozenset(), "strong": frozenset(),
    "i": frozenset(), "em": frozenset(),
    "u": frozenset(), "ins": frozenset(),
    "s": frozenset(), "strike": frozenset(), "del": frozenset(),
    "span": frozenset({"class"}),
    "tg-spoiler": frozenset(),
    "a": frozenset({"href"}),
    "code": frozenset({"class"}),
    "pre": frozenset(),
    "blockquote": frozenset({"expandable"}),
    "tg-emoji": frozenset({"emoji-id"}),
}


def _cant_parse(detail: str) -> ApiRuleViolation:
    return ApiRuleViolation(f"Bad Request: can't parse entities: {detail}")


def validate_html(text: str) -> None:
    stack: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "<":
            token = _TAG_TOKEN.match(text, i)
            if not token:
                snippet = text[i + 1 : i + 21].split(">", 1)[0] or "<"
                raise _cant_parse(f'Unsupported start tag "{snippet}"')
            closing, name, attrs_raw = token.group(1), token.group(2).lower(), token.group(3)
            if name not in _HTML_ALLOWED:
                raise _cant_parse(f'Unsupported start tag "{name}"')
            if closing:
                if not stack or stack[-1] != name:
                    raise _cant_parse(f'Unmatched end tag "{name}"')
                stack.pop()
            else:
                attrs = {
                    m.group(1).lower(): m.group(2) if m.group(2) is not None else m.group(3)
                    for m in _ATTR.finditer(attrs_raw)
                    if m.group(1)
                }
                unknown = set(attrs) - _HTML_ALLOWED[name]
                if unknown:
                    raise _cant_parse(
                        f'Unsupported attribute "{sorted(unknown)[0]}" in tag "{name}"'
                    )
                if name == "a" and "href" not in attrs:
                    raise _cant_parse('Tag "a" must have attribute "href"')
                if name == "span" and attrs.get("class") != "tg-spoiler":
                    raise _cant_parse('Tag "span" must have class "tg-spoiler"')
                if name == "tg-emoji" and not attrs.get("emoji-id"):
                    raise _cant_parse('Tag "tg-emoji" must have attribute "emoji-id"')
                stack.append(name)
            i = token.end()
        elif ch == "&":
            ref = _CHAR_REF.match(text, i)
            if not ref:
                raise _cant_parse("Unexpected character '&' (escape it as &amp;)")
            i = ref.end()
        else:
            i += 1
    if stack:
        raise _cant_parse(
            f'Can\'t find end tag corresponding to start tag "{stack[-1]}"'
        )


_MD2_RESERVED = frozenset("_*[]()~`>#+-=|{}.!")


def _reserved_char(ch: str) -> ApiRuleViolation:
    return _cant_parse(
        f"Character '{ch}' is reserved and must be escaped with the preceding '\\'"
    )


def validate_markdown(text: str, version: int) -> None:
    if version == 1:
        _validate_markdown_legacy(text)
    else:
        _validate_markdown_v2(text)


def _validate_markdown_v2(text: str) -> None:
    stack: list[str] = []
    line_is_quote = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "\n":
            line_is_quote = False
            i += 1
            continue
        in_code = bool(stack) and stack[-1] in ("`", "```")
        if ch == "`":
            seq = "```" if text.startswith("```", i) else "`"
            if in_code:
                if stack[-1] == seq:
                    stack.pop()
                    i += len(seq)
                    continue
                i += 1
                continue
            stack.append(seq)
            i += len(seq)
            continue
        if in_code:
            i += 1
            continue
        if text.startswith("**>", i) and (i == 0 or text[i - 1] == "\n"):
            # first line of an expandable blockquote starts with **> at line start
            line_is_quote = True
            i += 3
            continue
        if text.startswith("||", i):
            if stack and stack[-1] == "||":
                stack.pop()
            elif line_is_quote and (i + 2 == n or text[i + 2] == "\n"):
                pass  # expandability mark at the end of a quote's last line
            else:
                stack.append("||")
            i += 2
            continue
        if ch == "_":
            seq = "__" if text.startswith("__", i) else "_"
            if stack and stack[-1] == seq:
                stack.pop()
            else:
                stack.append(seq)
            i += len(seq)
            continue
        if ch in "*~":
            if stack and stack[-1] == ch:
                stack.pop()
            else:
                stack.append(ch)
            i += 1
            continue
        if text.startswith("![", i):
            # custom emoji: ![emoji](tg://emoji?id=...)
            i += 1  # the '[' at the next position enters the existing link logic
            continue
        if ch == "[":
            stack.append("[")
            i += 1
            continue
        if ch == "]" and stack and stack[-1] == "[":
            stack.pop()
            if text.startswith("(", i + 1):
                # inside the (...) of a link, ')' and '\' must be escaped;
                # honor backslash escapes while scanning for the closing ')'
                j = i + 2
                while j < n:
                    if text[j] == "\\":
                        j += 2
                    elif text[j] == ")":
                        break
                    else:
                        j += 1
                if j >= n:
                    raise _cant_parse("Can't find end of a URL")
                i = j + 1
                continue
            i += 1
            continue
        if ch == ">" and (i == 0 or text[i - 1] == "\n"):
            line_is_quote = True
            i += 1
            continue
        if ch == "|":
            # single '|' (the '||' case was handled above)
            raise _reserved_char("|")
        if ch in _MD2_RESERVED:
            raise _reserved_char(ch)
        i += 1
    if stack:
        raise _cant_parse(f"Can't find end of {stack[-1]} entity")


def _validate_markdown_legacy(text: str) -> None:
    stack: list[str] = []
    i, n = 0, len(text)
    while i < n:
        in_code = bool(stack) and stack[-1] in ("`", "```")
        ch = text[i]
        if ch == "\\" and not in_code:
            # legacy Markdown documents escaping _ * ` [ with a preceding '\';
            # inside code spans '\' is literal, so the skip must not apply there
            # (an unconditional skip would eat a closing '`' and false-reject).
            i += 2
            continue
        if ch == "`":
            seq = "```" if text.startswith("```", i) else "`"
            if stack and stack[-1] == seq:
                stack.pop()
            elif not in_code:
                stack.append(seq)
            i += len(seq)
            continue
        if not in_code and ch in "*_":
            if stack and stack[-1] == ch:
                stack.pop()
            else:
                stack.append(ch)
            i += 1
            continue
        i += 1
    if stack:
        raise _cant_parse(f"Can't find end of {stack[-1]} entity")


def _check_parse_mode(text: str, parse_mode: str | None) -> None:
    if parse_mode is None:
        return
    mode = parse_mode.upper()
    if mode == "HTML":
        validate_html(text)
    elif mode == "MARKDOWNV2":
        validate_markdown(text, 2)
    elif mode == "MARKDOWN":
        validate_markdown(text, 1)


def _check_entities(text: str, entities: list[Any]) -> None:
    limit = _utf16_len(text)
    for entity in entities:
        if entity.offset < 0 or entity.length < 0 or entity.offset + entity.length > limit:
            raise ApiRuleViolation(
                "Bad Request: can't parse entities: entity out of text bounds"
            )


def _check_body(bot: Bot, method: TelegramMethod[Any], text: str, entities: Any) -> None:
    if entities:
        _check_entities(text, entities)
        return  # real API ignores parse_mode when entities are supplied
    parse_mode = _resolve_parse_mode(bot, getattr(method, "parse_mode", None))
    _check_parse_mode(text, parse_mode)


# InlineKeyboardButton docs: "Exactly one of the fields other than text,
# icon_custom_emoji_id, and style must be used to specify the type of the button."
_BUTTON_ACTION_FIELDS = (
    "url", "callback_data", "web_app", "login_url",
    "switch_inline_query", "switch_inline_query_current_chat",
    "switch_inline_query_chosen_chat", "copy_text", "callback_game", "pay",
)


def _check_inline_keyboard(markup: InlineKeyboardMarkup) -> None:
    for row in markup.inline_keyboard:
        for button in row:
            actions = [
                field for field in _BUTTON_ACTION_FIELDS
                if getattr(button, field, None) is not None
            ]
            if len(actions) != 1:
                raise ApiRuleViolation(
                    "Bad Request: can't parse inline keyboard button: exactly "
                    "one of the optional fields must be used"
                )
            if button.callback_data is not None:
                size = len(button.callback_data.encode("utf-8"))
                if not 1 <= size <= 64:
                    raise ApiRuleViolation("Bad Request: BUTTON_DATA_INVALID")


def validate_method(bot: Bot, method: TelegramMethod[Any]) -> None:
    if isinstance(method, (SendMessage, EditMessageText)):
        text = method.text
        if not text:
            raise ApiRuleViolation("Bad Request: message text is empty")
        if _utf16_len(text) > MAX_TEXT:
            raise ApiRuleViolation("Bad Request: message is too long")
        _check_body(bot, method, text, getattr(method, "entities", None))

    caption = getattr(method, "caption", None)
    if isinstance(caption, str):
        if _utf16_len(caption) > MAX_CAPTION:
            raise ApiRuleViolation("Bad Request: media caption is too long")
        _check_body(bot, method, caption, getattr(method, "caption_entities", None))

    if isinstance(method, AnswerCallbackQuery) and isinstance(method.text, str):
        if _utf16_len(method.text) > MAX_CALLBACK_ANSWER:
            raise ApiRuleViolation("Bad Request: MESSAGE_TOO_LONG")

    markup = getattr(method, "reply_markup", None)
    if isinstance(markup, InlineKeyboardMarkup):
        _check_inline_keyboard(markup)
