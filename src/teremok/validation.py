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


def validate_markdown(text: str, version: int) -> None:  # replaced in the Markdown task
    return


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


def _check_inline_keyboard(markup: InlineKeyboardMarkup) -> None:
    return  # replaced in the keyboard task


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
