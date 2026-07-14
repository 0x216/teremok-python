"""Documented Bot API rules, enforced the way real Telegram enforces them.

Every rule here cites the Bot API docs (see docs/validation.md). Violations
raise ApiRuleViolation; MockedSession converts them into genuine
TelegramBadRequest via the same check_response route as real error responses.
"""

from __future__ import annotations

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


def validate_html(text: str) -> None:  # replaced in the HTML task
    return


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
