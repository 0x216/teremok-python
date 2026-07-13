from aiogram.types import CallbackQuery, Message, Update, User

from teremok.builders import (
    DEFAULT_USER_ID,
    MockCallbackQuery,
    MockMessageText,
    MockUpdate,
    MockUser,
    next_update_id,
)


def test_mock_user_defaults_and_overrides() -> None:
    user = MockUser()
    assert isinstance(user, User)
    assert user.id == DEFAULT_USER_ID and not user.is_bot
    assert MockUser(user_id=7, first_name="Ann").first_name == "Ann"


def test_mock_message_text_defaults() -> None:
    msg = MockMessageText("/start")
    assert isinstance(msg, Message)
    assert msg.text == "/start"
    assert msg.chat.id == DEFAULT_USER_ID and msg.chat.type == "private"
    assert msg.from_user is not None and msg.from_user.id == DEFAULT_USER_ID


def test_message_ids_are_unique() -> None:
    assert MockMessageText("a").message_id != MockMessageText("b").message_id


def test_kwargs_pass_through_to_message() -> None:
    msg = MockMessageText("hi", message_thread_id=99, media_group_id="g1")
    assert msg.message_thread_id == 99
    assert msg.media_group_id == "g1"


def test_mock_callback_query() -> None:
    cb = MockCallbackQuery(data="confirm")
    assert isinstance(cb, CallbackQuery)
    assert cb.data == "confirm"
    assert isinstance(cb.message, Message)
    assert cb.from_user.id == DEFAULT_USER_ID
    # default message contract: authored by the bot, in the caller's chat
    assert cb.message.from_user is not None and cb.message.from_user.is_bot
    assert cb.message.from_user.id == 42
    assert cb.message.chat.id == cb.from_user.id
    assert cb.chat_instance == "test_chat_instance"


def test_mock_update_escape_hatch() -> None:
    msg = MockMessageText("edited!")
    upd = MockUpdate(edited_message=msg)
    assert isinstance(upd, Update)
    assert upd.edited_message is msg and upd.message is None


def test_update_ids_monotonic() -> None:
    assert next_update_id() < next_update_id()
