from __future__ import annotations

import types
import typing
from collections.abc import Callable
from datetime import datetime, timezone
from itertools import count
from typing import Any, Union

from aiogram import Bot
from aiogram.methods import (
    CopyMessage,
    EditMessageCaption,
    EditMessageReplyMarkup,
    EditMessageText,
    ForwardMessage,
    GetFile,
    GetMe,
    SendAnimation,
    SendAudio,
    SendDocument,
    SendMediaGroup,
    SendMessage,
    SendPhoto,
    SendVideo,
    SendVoice,
    TelegramMethod,
)
from aiogram.types import Chat, File, InlineKeyboardMarkup, Message, MessageId, User

FilesDict = dict[str, tuple[str, bytes]]


class CannotAutoRespond(AssertionError):
    """The method's return type cannot be synthesized; queue a result instead."""


def _is_bool(returning: Any) -> bool:
    return returning is bool


def _message_in(returning: Any) -> bool:
    if returning is Message:
        return True
    # aiogram declares some `__returning__` unions with `Message | bool` and
    # others with `Union[Message, bool]`; depending on the Python version the
    # former's get_origin() is types.UnionType while the latter's is
    # typing.Union, so both must be checked.
    if typing.get_origin(returning) in (Union, types.UnionType):
        return Message in typing.get_args(returning)
    return False


class AutoResponder:
    """Synthesizes plausible API results for un-queued calls."""

    def __init__(self) -> None:
        self._message_ids: dict[Any, count[int]] = {}

    def next_message_id(self, chat_id: Any) -> int:
        return next(self._message_ids.setdefault(chat_id, count(1)))

    def bot_user(self, bot: Bot) -> User:
        return User(id=bot.id, is_bot=True, first_name="TestBot", username="test_bot")

    def make_chat(self, chat_id: Any) -> Chat:
        if isinstance(chat_id, int):
            return Chat(id=chat_id, type="private")
        return Chat(id=0, type="channel", title=str(chat_id))

    def make_message(
        self, bot: Bot, method: TelegramMethod[Any], message_id: int | None = None
    ) -> Message:
        chat_id = getattr(method, "chat_id", 12345)
        # An edit keeps the original message_id (like Telegram): callers pass
        # the method's message_id so a fresh id is NOT allocated for edits.
        data: dict[str, Any] = {
            "message_id": message_id
            if message_id is not None
            else self.next_message_id(chat_id),
            "date": datetime.now(timezone.utc),
            "chat": self.make_chat(chat_id),
            "from_user": self.bot_user(bot),
        }
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            if value is not None:
                data[field] = value
        markup = getattr(method, "reply_markup", None)
        if isinstance(markup, InlineKeyboardMarkup):
            # Message.reply_markup only accepts inline keyboards; reply
            # keyboards are visible on the captured method, not the result.
            data["reply_markup"] = markup
        return Message(**data)

    def make_file(self, method: GetFile, files: FilesDict) -> File:
        file_id = method.file_id
        file_path, data = files.get(file_id, (f"files/{file_id}.dat", b""))
        return File(
            file_id=file_id,
            file_unique_id=f"u_{file_id}",
            file_size=len(data),
            file_path=file_path,
        )

    def respond(self, bot: Bot, method: TelegramMethod[Any], files: FilesDict) -> Any:
        handler = CURATED.get(type(method))
        if handler is not None:
            return handler(self, bot, method, files)
        returning = type(method).__returning__
        if _is_bool(returning):
            return True
        if _message_in(returning):
            return self.make_message(bot, method)
        raise CannotAutoRespond(
            f"teremok cannot auto-generate a result for {type(method).__name__} "
            f"(returns {returning!r}); queue one with add_result(...)"
        )


def _h_message(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    return r.make_message(bot, m)


def _h_edit(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    # Editing a chat message returns the edited Message, keeping its id;
    # editing an inline message (inline_message_id, no chat message) returns
    # True - both are real Bot API behaviours for the edit-* family.
    if getattr(m, "inline_message_id", None) is not None and getattr(m, "message_id", None) is None:
        return True
    return r.make_message(bot, m, message_id=getattr(m, "message_id", None))


def _h_get_me(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    return r.bot_user(bot)


def _h_get_file(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    assert isinstance(m, GetFile)
    return r.make_file(m, files)


def _h_media_group(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    media = getattr(m, "media", []) or []
    return [r.make_message(bot, m) for _ in media]


def _h_message_id(r: AutoResponder, bot: Bot, m: TelegramMethod[Any], files: FilesDict) -> Any:
    return MessageId(message_id=r.next_message_id(getattr(m, "chat_id", 12345)))


Handler = Callable[[AutoResponder, Bot, TelegramMethod[Any], FilesDict], Any]

CURATED: dict[type, Handler] = {
    SendMessage: _h_message,
    SendPhoto: _h_message,
    SendDocument: _h_message,
    SendVoice: _h_message,
    SendVideo: _h_message,
    SendAudio: _h_message,
    SendAnimation: _h_message,
    ForwardMessage: _h_message,
    EditMessageText: _h_edit,
    EditMessageCaption: _h_edit,
    EditMessageReplyMarkup: _h_edit,
    GetMe: _h_get_me,
    GetFile: _h_get_file,
    SendMediaGroup: _h_media_group,
    CopyMessage: _h_message_id,
}


def classify(method_cls: type) -> str:
    """Coverage tier for a TelegramMethod subclass: curated | generic | planned."""
    if method_cls in CURATED:
        return "curated"
    returning = getattr(method_cls, "__returning__", None)
    if _is_bool(returning) or _message_in(returning):
        return "generic"
    return "planned"
