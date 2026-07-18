"""Callback-answer discipline (v0.3.0).

These tests pin the exact production bug class teremok used to wave through: a
callback handler that never calls ``callback.answer()`` leaves an endless
loading spinner on the button in real Telegram, and answering the same query
twice gets a 400. MockBot auto-acks every callback with no once-tracking, so
both bugs pass a green test - unless strict-answer is on.
"""

from __future__ import annotations

import pytest
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from teremok import CallbackNotAnswered, MockBot, MockCallbackQuery, MockMessageText


def make_router() -> Router:
    router = Router()

    @router.callback_query(F.data == "answered")
    async def good(callback: CallbackQuery) -> None:
        await callback.answer()  # the spinner-clearing ack a real bot must send

    @router.callback_query(F.data == "silent")
    async def bad(callback: CallbackQuery) -> None:
        # Edits the screen but forgets to answer -> eternal spinner in prod.
        assert isinstance(callback.message, Message)
        await callback.message.edit_text("updated")

    @router.callback_query(F.data == "double")
    async def double(callback: CallbackQuery) -> None:
        await callback.answer("first")
        await callback.answer("second")  # second ack -> 400 in real Telegram

    return router


# --- the headline regression: unanswered callback fails only in strict mode ---


async def test_unanswered_callback_fails_strict_session() -> None:
    bot = MockBot(make_router(), strict_answer=True)
    with pytest.raises(CallbackNotAnswered, match="never answered"):
        await bot.dispatch(MockCallbackQuery(data="silent"))


async def test_unanswered_callback_passes_when_not_strict() -> None:
    # Backward-compatible default: the old blind spot stays green so existing
    # suites don't break on upgrade (opt in with strict_answer=True).
    bot = MockBot(make_router())
    result = await bot.dispatch(MockCallbackQuery(data="silent"))
    assert result.handled
    assert result.answered is False


async def test_answered_callback_passes_strict_session() -> None:
    bot = MockBot(make_router(), strict_answer=True)
    result = await bot.dispatch(MockCallbackQuery(data="answered"))
    assert result.handled
    assert result.answered is True


# --- answer-once rule (a second answer is a real 400) ------------------------


async def test_double_answer_raises_in_strict_mode() -> None:
    bot = MockBot(make_router(), strict_answer=True)
    with pytest.raises(TelegramBadRequest, match="query is too old"):
        await bot.dispatch(MockCallbackQuery(data="double"))


async def test_double_answer_tolerated_when_not_strict() -> None:
    # Default stays lenient (backward compatible); only the once-tracking set
    # records the id. Flip strict_answer=True to make the duplicate a failure.
    bot = MockBot(make_router())
    result = await bot.dispatch(MockCallbackQuery(data="double"))
    assert result.handled
    assert len(bot.requests.answer_callback_query) == 2


# --- per-step assertion API, usable without global strictness ----------------


async def test_assert_answered_on_result() -> None:
    bot = MockBot(make_router())
    good = await bot.dispatch(MockCallbackQuery(data="answered"))
    good.assert_answered()  # no raise

    bad = await bot.dispatch(MockCallbackQuery(data="silent"))
    with pytest.raises(AssertionError, match="never answered"):
        bad.assert_answered()


async def test_assert_answered_requires_a_callback() -> None:
    bot = MockBot(make_router())
    result = await bot.dispatch(MockMessageText("not a callback"))
    assert result.callback_query_id is None
    with pytest.raises(AssertionError, match="only applies to a dispatched callback_query"):
        result.assert_answered()


# --- strict-answer must not misfire ------------------------------------------


async def test_strict_answer_ignores_plain_messages() -> None:
    router = Router()

    @router.message()
    async def echo(message: Message) -> None:
        await message.answer("hi")  # no callback to answer; must not fail

    bot = MockBot(router, strict_answer=True)
    result = await bot.dispatch(MockMessageText("ping"))
    assert result.handled and result.answered is False


async def test_strict_answer_ignores_unhandled_callback() -> None:
    # Nothing matched -> the bot ran no handler, so there is nothing to answer;
    # strict-answer only polices callbacks a handler actually took.
    bot = MockBot(Router(), strict_answer=True)
    result = await bot.dispatch(MockCallbackQuery(data="nobody-handles-this"))
    assert not result.handled


async def test_session_records_answered_ids() -> None:
    bot = MockBot(make_router())
    query = MockCallbackQuery(data="answered")
    await bot.dispatch(query)
    assert query.id in bot.mock_session.answered_callbacks
