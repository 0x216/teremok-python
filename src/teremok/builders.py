from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any

from aiogram.types import CallbackQuery, Chat, Document, Message, PhotoSize, Update, User, Voice

DEFAULT_USER_ID = 12345

_update_ids = count(1)
_message_ids = count(1)
_callback_ids = count(1)


def next_update_id() -> int:
    return next(_update_ids)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def MockUser(
    user_id: int = DEFAULT_USER_ID,
    first_name: str = "Test",
    username: str = "test_user",
    **kwargs: Any,
) -> User:
    return User(
        id=user_id, is_bot=False, first_name=first_name, username=username, **kwargs
    )


def MockChat(chat_id: int = DEFAULT_USER_ID, type: str = "private", **kwargs: Any) -> Chat:
    return Chat(id=chat_id, type=type, **kwargs)


def MockMessageText(
    text: str = "test",
    user: User | None = None,
    chat: Chat | None = None,
    **kwargs: Any,
) -> Message:
    user = user or MockUser()
    chat = chat or MockChat(chat_id=user.id)
    return Message(
        message_id=next(_message_ids),
        date=_now(),
        chat=chat,
        from_user=user,
        text=text,
        **kwargs,
    )


def MockCallbackQuery(
    data: str = "test",
    user: User | None = None,
    message: Message | None = None,
    **kwargs: Any,
) -> CallbackQuery:
    user = user or MockUser()
    if message is None:
        bot_user = User(id=42, is_bot=True, first_name="TestBot", username="test_bot")
        message = MockMessageText(
            "message with buttons", user=bot_user, chat=MockChat(chat_id=user.id)
        )
    return CallbackQuery(
        id=str(next(_callback_ids)),
        from_user=user,
        chat_instance="test_chat_instance",
        message=message,
        data=data,
        **kwargs,
    )


def MockUpdate(**kwargs: Any) -> Update:
    return Update(update_id=next_update_id(), **kwargs)


def MockMessagePhoto(
    file_id: str = "photo_file_1",
    caption: str | None = None,
    user: User | None = None,
    chat: Chat | None = None,
    **kwargs: Any,
) -> Message:
    user = user or MockUser()
    chat = chat or MockChat(chat_id=user.id)
    photo = [
        PhotoSize(
            file_id=file_id,
            file_unique_id=f"u_{file_id}",
            width=1280,
            height=960,
            file_size=1024,
        )
    ]
    return Message(
        message_id=next(_message_ids),
        date=_now(),
        chat=chat,
        from_user=user,
        photo=photo,
        caption=caption,
        **kwargs,
    )


def MockMessageDocument(
    file_id: str = "doc_file_1",
    file_name: str = "file.pdf",
    caption: str | None = None,
    user: User | None = None,
    chat: Chat | None = None,
    **kwargs: Any,
) -> Message:
    user = user or MockUser()
    chat = chat or MockChat(chat_id=user.id)
    document = Document(
        file_id=file_id,
        file_unique_id=f"u_{file_id}",
        file_name=file_name,
        file_size=2048,
    )
    return Message(
        message_id=next(_message_ids),
        date=_now(),
        chat=chat,
        from_user=user,
        document=document,
        caption=caption,
        **kwargs,
    )


def MockMessageVoice(
    file_id: str = "voice_file_1",
    duration: int = 3,
    user: User | None = None,
    chat: Chat | None = None,
    **kwargs: Any,
) -> Message:
    user = user or MockUser()
    chat = chat or MockChat(chat_id=user.id)
    voice = Voice(
        file_id=file_id,
        file_unique_id=f"u_{file_id}",
        duration=duration,
        file_size=4096,
    )
    return Message(
        message_id=next(_message_ids),
        date=_now(),
        chat=chat,
        from_user=user,
        voice=voice,
        **kwargs,
    )
