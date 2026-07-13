import pytest
from aiogram import Bot
from aiogram.methods import (
    AnswerCallbackQuery,
    CopyMessage,
    GetUpdates,
    SendMediaGroup,
    SendMessage,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from teremok.responses import CannotAutoRespond, classify
from teremok.session import MockedSession


def make_bot() -> Bot:
    return Bot("42:TEST", session=MockedSession())


async def test_send_message_synthesizes_message_echoing_fields() -> None:
    bot = make_bot()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Go", callback_data="go")]]
    )
    msg = await bot.send_message(chat_id=100, text="hello", reply_markup=kb)
    assert msg.text == "hello"
    assert msg.chat.id == 100
    # Compare field content, not `==`: check_response deserializes results via
    # model_validate(..., context={"bot": bot}), which binds a private _bot
    # context onto reply_markup recursively. pydantic's __eq__ compares that
    # private context too, so the rebuilt (bot-bound) markup can never `==`
    # the original (unbound) literal -- this is genuine aiogram behavior that
    # would occur identically against a real Telegram API response.
    assert msg.reply_markup is not None
    assert msg.reply_markup.model_dump() == kb.model_dump()
    assert msg.from_user is not None and msg.from_user.is_bot


async def test_message_ids_increment_per_chat_not_globally() -> None:
    bot = make_bot()
    a1 = await bot.send_message(chat_id=1, text="x")
    b1 = await bot.send_message(chat_id=2, text="x")
    a2 = await bot.send_message(chat_id=1, text="x")
    assert (a1.message_id, a2.message_id) == (1, 2)
    assert b1.message_id == 1


async def test_bool_returning_methods_auto_answer_true() -> None:
    bot = make_bot()
    assert await bot.answer_callback_query(callback_query_id="1") is True
    assert await bot.delete_message(chat_id=1, message_id=1) is True


async def test_get_me_returns_bot_user() -> None:
    bot = make_bot()
    me = await bot.get_me()
    assert me.id == bot.id and me.is_bot


async def test_copy_message_returns_message_id() -> None:
    bot = make_bot()
    result = await bot.copy_message(chat_id=1, from_chat_id=2, message_id=5)
    assert result.message_id >= 1


async def test_unknown_complex_method_raises_helpful_error() -> None:
    bot = make_bot()
    with pytest.raises(CannotAutoRespond, match="GetUpdates.*add_result"):
        await bot.get_updates()


def test_classify_tiers() -> None:
    assert classify(SendMessage) == "curated"
    assert classify(SendMediaGroup) == "curated"
    assert classify(CopyMessage) == "curated"
    assert classify(AnswerCallbackQuery) == "generic"
    assert classify(GetUpdates) == "planned"
