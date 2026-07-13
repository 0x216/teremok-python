from datetime import datetime, timezone

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe, SendMessage
from aiogram.methods.base import Response
from aiogram.types import Chat, Message, User

from teremok.session import MockedSession, NoResultQueued


def make_bot(**kwargs) -> Bot:
    return Bot("42:TEST", session=MockedSession(**kwargs))


def make_message(text: str = "ok") -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=1, type="private"),
        text=text,
    )


async def test_captures_requests_in_order() -> None:
    bot = make_bot()
    bot.session.add_result(
        SendMessage, Response[SendMessage.__returning__](ok=True, result=make_message("one"))
    )
    bot.session.add_result(
        SendMessage, Response[SendMessage.__returning__](ok=True, result=make_message("two"))
    )
    await bot.send_message(chat_id=1, text="one")
    await bot.send_message(chat_id=1, text="two")
    captured = bot.session.requests
    assert [m.text for m in captured] == ["one", "two"]
    assert all(isinstance(m, SendMessage) for m in captured)


async def test_queued_result_is_returned() -> None:
    bot = make_bot()
    me = User(id=42, is_bot=True, first_name="Queued")
    bot.session.add_result(GetMe, Response[GetMe.__returning__](ok=True, result=me))
    result = await bot.get_me()
    assert result.first_name == "Queued"


async def test_queued_error_raises_telegram_exception() -> None:
    bot = make_bot()
    bot.session.add_result(
        SendMessage,
        Response[SendMessage.__returning__](
            ok=False, error_code=400, description="Bad Request: chat not found"
        ),
    )
    with pytest.raises(TelegramBadRequest, match="chat not found"):
        await bot.send_message(chat_id=999, text="hi")


async def test_strict_mode_raises_without_queued_result() -> None:
    bot = make_bot(strict=True)
    with pytest.raises(NoResultQueued, match="SendMessage"):
        await bot.send_message(chat_id=1, text="hi")


async def test_queued_result_is_bound_to_bot_for_chaining() -> None:
    bot = make_bot()
    bot.session.add_result(
        SendMessage, Response[SendMessage.__returning__](ok=True, result=make_message("hi"))
    )
    sent = await bot.send_message(chat_id=1, text="hi")
    # chaining API calls off a mocked result must work like with a real session
    from aiogram.methods import DeleteMessage

    bot.session.add_result(
        DeleteMessage, Response[DeleteMessage.__returning__](ok=True, result=True)
    )
    assert await sent.delete() is True
