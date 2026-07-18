"""Message-id + edit + stale-message lifecycle (v0.3.0).

Models the on-screen message history faithfully enough to reach a handler's
"screen out of date" branch: edits keep their message_id (like Telegram), the
bot's sent/edited messages are recorded in order, and a test can tap a button
on an EARLIER (now-stale) message instead of only the latest one - the menu
freshness bug class that a fresh-every-time carrier message could never
exercise.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from teremok import MockBot, MockCallbackQuery, MockMessageText


def _kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Next", callback_data="nav")]]
    )


# --- edit keeps the message id (responses-level) -----------------------------


async def test_edit_message_text_keeps_id() -> None:
    bot = MockBot(Router())
    edited = await bot.edit_message_text(chat_id=1, message_id=99, text="v2")
    assert isinstance(edited, Message)
    assert edited.message_id == 99  # NOT a freshly allocated id
    assert edited.text == "v2"


async def test_edit_reply_markup_keeps_id() -> None:
    bot = MockBot(Router())
    edited = await bot.edit_message_reply_markup(chat_id=1, message_id=77, reply_markup=_kb())
    assert isinstance(edited, Message)
    assert edited.message_id == 77


async def test_inline_message_edit_returns_true() -> None:
    # Editing an inline message (inline_message_id, no chat message) returns
    # True in the real Bot API, not a Message.
    bot = MockBot(Router())
    assert await bot.edit_message_text(inline_message_id="inline-abc", text="v2") is True


# --- sent-message history ----------------------------------------------------


async def test_sent_messages_records_sends_and_edits_in_order() -> None:
    bot = MockBot(Router())
    first = await bot.send_message(chat_id=1, text="one")
    await bot.edit_message_text(chat_id=1, message_id=first.message_id, text="one-edited")
    second = await bot.send_message(chat_id=1, text="two")

    ids = [m.message_id for m in bot.sent_messages]
    # send #1, its edit (same id), send #2 (new id) - the edit did not burn an id.
    assert ids == [first.message_id, first.message_id, second.message_id]
    assert first.message_id != second.message_id
    assert bot.last_message is not None and bot.last_message.text == "two"


# --- the headline regression: tap a button on a stale message ----------------


def _menu_router() -> Router:
    router = Router()

    class Menu(StatesGroup):
        open = State()

    @router.message(Command("menu"))
    async def open_menu(message: Message, state: FSMContext) -> None:
        sent = await message.answer("screen 1", reply_markup=_kb())
        await state.update_data(menu_id=sent.message_id)

    @router.callback_query(F.data == "nav")
    async def nav(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        assert isinstance(callback.message, Message)
        if callback.message.message_id != data.get("menu_id"):
            # The tapped button belongs to an old screen the bot has moved on
            # from - the exact "screen out of date" guard live bots ship.
            await callback.answer("screen out of date", show_alert=True)
            return
        fresh = await callback.message.answer("screen 2", reply_markup=_kb())
        await state.update_data(menu_id=fresh.message_id)
        await callback.answer()

    return router


async def test_tapping_a_stale_message_hits_the_out_of_date_branch() -> None:
    bot = MockBot(_menu_router(), strict_answer=True)

    # 1. Open the menu; grab the real message the buttons are attached to.
    await bot.dispatch(MockMessageText("/menu"))
    screen1 = bot.sent_messages[-1]
    assert screen1.text == "screen 1"

    # 2. Tap Next on the CURRENT screen -> fresh: a new screen (new id) is sent.
    fresh = await bot.dispatch(MockCallbackQuery(data="nav", message=screen1))
    fresh.assert_answered()
    screen2 = bot.sent_messages[-1]
    assert screen2.text == "screen 2"
    assert screen2.message_id != screen1.message_id

    # 3. Tap Next again on the NOW-STALE screen 1 -> the out-of-date branch,
    #    reachable only because teremok let us re-use the earlier message.
    stale = await bot.dispatch(MockCallbackQuery(data="nav", message=screen1))
    alerts = [
        m.text
        for m in stale.requests.answer_callback_query
        if getattr(m, "show_alert", False)
    ]
    assert alerts == ["screen out of date"]
    # No new screen was pushed for the stale tap.
    assert bot.sent_messages[-1].text == "screen 2"
