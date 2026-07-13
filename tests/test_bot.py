import pytest
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Message

from teremok import MockBot, MockCallbackQuery, MockMessageText, MockUpdate


def make_router() -> Router:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer("Hello!")

    @router.callback_query(F.data == "confirm")
    async def on_confirm(callback: CallbackQuery) -> None:
        await callback.answer("Confirmed")
        assert isinstance(callback.message, Message)
        await callback.message.answer("Done")

    return router


async def test_dispatch_message_and_capture_typed() -> None:
    bot = MockBot(make_router())
    result = await bot.dispatch(MockMessageText("/start"))
    assert result.handled
    sent = bot.requests.send_message
    assert len(sent) == 1
    assert isinstance(sent[0], SendMessage)
    assert sent[0].text == "Hello!"


async def test_dispatch_callback_query() -> None:
    bot = MockBot(make_router())
    result = await bot.dispatch(MockCallbackQuery(data="confirm"))
    assert result.handled
    assert bot.requests.answer_callback_query[0].text == "Confirmed"
    assert bot.requests.send_message[0].text == "Done"


async def test_unhandled_update() -> None:
    bot = MockBot(Router())
    result = await bot.dispatch(MockMessageText("nobody handles this"))
    assert not result.handled
    assert bot.requests.all == []


async def test_per_dispatch_request_slices() -> None:
    bot = MockBot(make_router())
    first = await bot.dispatch(MockMessageText("/start"))
    second = await bot.dispatch(MockMessageText("/start"))
    assert len(first.requests.all) == 1
    assert len(second.requests.all) == 1
    assert len(bot.requests.all) == 2
    assert bot.last is second


async def test_edited_message_via_mock_update() -> None:
    router = Router()

    @router.edited_message()
    async def on_edit(message: Message) -> None:
        await message.answer("saw the edit")

    bot = MockBot(router)
    result = await bot.dispatch(MockUpdate(edited_message=MockMessageText("v2")))
    assert result.handled
    assert bot.requests.send_message[0].text == "saw the edit"


async def test_dispatch_kwargs_reach_handlers_as_di() -> None:
    router = Router()

    @router.message()
    async def needs_config(message: Message, app_config: dict) -> None:
        await message.answer(app_config["greeting"])

    bot = MockBot(router)
    await bot.dispatch(MockMessageText("hi"), app_config={"greeting": "yo"})
    assert bot.requests.send_message[0].text == "yo"


async def test_add_result_queues_api_error() -> None:
    bot = MockBot(make_router())
    bot.add_result(
        SendMessage, ok=False, error_code=400, description="Bad Request: chat not found"
    )
    with pytest.raises(TelegramBadRequest, match="chat not found"):
        await bot.dispatch(MockMessageText("/start"))


async def test_add_result_targets_specific_method_not_call_order() -> None:
    """Reviewer's probe: on_confirm calls callback.answer() (AnswerCallbackQuery)
    BEFORE callback.message.answer() (SendMessage). A result queued for
    SendMessage must raise from the SendMessage call, not misroute to the
    earlier AnswerCallbackQuery call - queues are keyed per method type."""
    reached_send_message = False
    router = Router()

    @router.callback_query(F.data == "confirm")
    async def on_confirm(callback: CallbackQuery) -> None:
        await callback.answer("ack")  # AnswerCallbackQuery - must auto-succeed
        nonlocal reached_send_message
        reached_send_message = True
        assert isinstance(callback.message, Message)
        await callback.message.answer("reply")  # SendMessage - must raise

    bot = MockBot(router)
    bot.add_result(
        SendMessage, ok=False, error_code=400, description="Bad Request: chat not found"
    )
    with pytest.raises(TelegramBadRequest, match="chat not found"):
        await bot.dispatch(MockCallbackQuery(data="confirm"))
    # The handler must have gotten PAST callback.answer() before raising -
    # if the queued SendMessage error had misrouted to AnswerCallbackQuery
    # (the old global-FIFO bug), the exception would fire before this flag
    # is ever set.
    assert reached_send_message, "exception fired from AnswerCallbackQuery, not SendMessage"
    answered = bot.requests.answer_callback_query
    assert len(answered) == 1
    assert all(isinstance(m, AnswerCallbackQuery) for m in answered)


async def test_add_result_ok_response_keyed_to_its_own_method() -> None:
    """Ok-result mirror of the probe above: queuing a valid SendMessage result
    must not misroute into the earlier AnswerCallbackQuery call (which returns
    bool, not Message) - that would raise ClientDecodeError instead of the
    earlier call auto-answering and the later call returning the queued
    result."""
    returned: Message | None = None
    router = Router()

    @router.callback_query(F.data == "confirm")
    async def on_confirm(callback: CallbackQuery) -> None:
        await callback.answer("ack")
        nonlocal returned
        assert isinstance(callback.message, Message)
        returned = await callback.message.answer("reply")

    bot = MockBot(router)
    bot.add_result(SendMessage, MockMessageText("custom reply"))
    result = await bot.dispatch(MockCallbackQuery(data="confirm"))
    assert result.handled
    assert bot.requests.answer_callback_query[0].text == "ack"
    assert returned is not None and returned.text == "custom reply"


def test_unknown_method_name_raises_attribute_error() -> None:
    bot = MockBot(Router())
    with pytest.raises(AttributeError, match="snd_message"):
        _ = bot.requests.snd_message


def test_non_method_reexports_raise_attribute_error() -> None:
    bot = MockBot(Router())
    for name in ("request", "response", "telegram_method"):
        with pytest.raises(AttributeError, match=name):
            getattr(bot.requests, name)
