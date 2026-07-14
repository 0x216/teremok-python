import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import MessageEntity

from teremok import MockBot


def make_bot(**kwargs) -> MockBot:
    return MockBot(Router(), **kwargs)


async def test_empty_text_rejected_like_real_api() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message text is empty"):
        await bot.send_message(chat_id=1, text="")


async def test_text_over_4096_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message is too long"):
        await bot.send_message(chat_id=1, text="x" * 4097)


async def test_text_exactly_4096_passes() -> None:
    bot = make_bot()
    msg = await bot.send_message(chat_id=1, text="x" * 4096)
    assert msg.message_id >= 1


async def test_length_counted_in_utf16_units() -> None:
    bot = make_bot()
    # emoji outside BMP = 2 UTF-16 units: 2048 emoji = 4096 units -> passes
    await bot.send_message(chat_id=1, text="😀" * 2048)
    # 2049 emoji = 4098 units -> rejected
    with pytest.raises(TelegramBadRequest, match="too long"):
        await bot.send_message(chat_id=1, text="😀" * 2049)


async def test_caption_over_1024_rejected_and_boundary_passes() -> None:
    bot = make_bot()
    from aiogram.types import BufferedInputFile

    photo = BufferedInputFile(b"x", filename="p.jpg")
    await bot.send_photo(chat_id=1, photo=photo, caption="c" * 1024)
    with pytest.raises(TelegramBadRequest, match="caption is too long"):
        await bot.send_photo(chat_id=1, photo=photo, caption="c" * 1025)


async def test_edit_message_text_validated_too() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message text is empty"):
        await bot.edit_message_text(chat_id=1, message_id=1, text="")


async def test_answer_callback_query_text_limit_200() -> None:
    bot = make_bot()
    await bot.answer_callback_query(callback_query_id="1", text="t" * 200)
    with pytest.raises(TelegramBadRequest, match="MESSAGE_TOO_LONG"):
        await bot.answer_callback_query(callback_query_id="1", text="t" * 201)


async def test_entity_out_of_range_rejected() -> None:
    bot = make_bot()
    entity = MessageEntity(type="bold", offset=3, length=10)
    with pytest.raises(TelegramBadRequest, match="entit"):
        await bot.send_message(chat_id=1, text="hello", entities=[entity])


async def test_entity_in_range_passes_with_utf16_offsets() -> None:
    bot = make_bot()
    text = "😀 bold"  # emoji = 2 units, space at 2, 'bold' at 3..7
    entity = MessageEntity(type="bold", offset=3, length=4)
    msg = await bot.send_message(chat_id=1, text=text, entities=[entity])
    assert msg.message_id >= 1


async def test_validation_off_escape_hatch() -> None:
    bot = make_bot(validate=False)
    msg = await bot.send_message(chat_id=1, text="x" * 5000)
    assert msg.message_id >= 1


async def test_offending_method_still_captured() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest):
        await bot.send_message(chat_id=1, text="")
    assert len(bot.requests.send_message) == 1


async def test_default_parse_mode_is_validated() -> None:
    from aiogram.client.default import DefaultBotProperties

    bot = MockBot(Router(), default=DefaultBotProperties(parse_mode="HTML"))
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await bot.send_message(chat_id=1, text="<b>broken")
