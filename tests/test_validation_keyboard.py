import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


def kb(*buttons: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(buttons)])


async def send_kb(bot: MockBot, markup: InlineKeyboardMarkup) -> None:
    await bot.send_message(chat_id=1, text="menu", reply_markup=markup)


async def test_valid_buttons_pass() -> None:
    bot = make_bot()
    await send_kb(
        bot,
        kb(
            InlineKeyboardButton(text="cb", callback_data="x" * 64),
            InlineKeyboardButton(text="url", url="https://example.com"),
            InlineKeyboardButton(text="inline", switch_inline_query=""),
        ),
    )


async def test_callback_data_over_64_bytes_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="x" * 65)))


async def test_callback_data_counted_in_bytes_not_chars() -> None:
    bot = make_bot()
    # 33 Cyrillic chars = 66 UTF-8 bytes -> rejected
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="я" * 33)))
    # 32 Cyrillic chars = 64 bytes -> passes
    await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="я" * 32)))


async def test_empty_callback_data_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="")))


async def test_button_with_no_action_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="inline keyboard button"):
        await send_kb(bot, kb(InlineKeyboardButton(text="dead button")))


async def test_button_with_two_actions_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="inline keyboard button"):
        await send_kb(
            bot,
            kb(
                InlineKeyboardButton(
                    text="both", callback_data="x", url="https://example.com"
                )
            ),
        )


async def test_edited_keyboard_validated_too() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await bot.edit_message_reply_markup(
            chat_id=1, message_id=1,
            reply_markup=kb(InlineKeyboardButton(text="x", callback_data="x" * 65)),
        )
