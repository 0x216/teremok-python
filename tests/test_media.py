from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, Message

from teremok import (
    MockBot,
    MockMessageDocument,
    MockMessagePhoto,
    MockMessageVoice,
)


def photo_router() -> Router:
    router = Router()

    @router.message(F.photo)
    async def handle_photo(message: Message, bot: Bot) -> None:
        content = await bot.download(message.photo[-1].file_id)
        assert content is not None
        data = content.read()
        await message.answer(f"{len(data)} bytes")
        await message.answer_photo(
            BufferedInputFile(data, filename="echo.jpg"), caption="Echo!"
        )

    return router


async def test_incoming_photo_download_and_typed_outgoing_capture() -> None:
    bot = MockBot(photo_router())
    bot.add_file("photo_1", b"JPEG_BYTES")
    result = await bot.dispatch(MockMessagePhoto(file_id="photo_1", caption="lunch"))
    assert result.handled
    assert bot.requests.send_message[0].text == "10 bytes"
    photo_req = bot.requests.send_photo[0]
    assert isinstance(photo_req.photo, BufferedInputFile)
    assert photo_req.photo.filename == "echo.jpg"
    assert photo_req.photo.data == b"JPEG_BYTES"
    assert photo_req.caption == "Echo!"
    # get_file was called under the hood and is captured too
    assert bot.requests.get_file[0].file_id == "photo_1"


async def test_download_unregistered_file_yields_empty() -> None:
    bot = MockBot(photo_router())
    await bot.dispatch(MockMessagePhoto(file_id="never_registered"))
    assert bot.requests.send_message[0].text == "0 bytes"


def test_document_and_voice_builders() -> None:
    doc = MockMessageDocument(file_name="report.pdf", caption="here")
    assert doc.document is not None and doc.document.file_name == "report.pdf"
    assert doc.caption == "here"
    voice = MockMessageVoice(duration=7)
    assert voice.voice is not None and voice.voice.duration == 7


async def test_multiple_files_with_suffix_overlapping_paths() -> None:
    router = Router()

    @router.message(F.photo)
    async def handle(message: Message, bot: Bot) -> None:
        content = await bot.download(message.photo[-1].file_id)
        assert content is not None
        await message.answer(content.read().decode())

    bot = MockBot(router)
    bot.add_file("a", b"AAAA", file_path="shared/name.jpg")
    bot.add_file("b", b"BBBB", file_path="other/shared/name.jpg")
    await bot.dispatch(MockMessagePhoto(file_id="a"))
    await bot.dispatch(MockMessagePhoto(file_id="b"))
    texts = [m.text for m in bot.requests.send_message]
    assert texts == ["AAAA", "BBBB"]


async def test_media_group_auto_response_returns_message_per_item() -> None:
    from aiogram.types import InputMediaPhoto

    bot = MockBot()
    media = [
        InputMediaPhoto(media="id1"),
        InputMediaPhoto(media="id2"),
    ]
    result = await bot.send_media_group(chat_id=1, media=media)
    assert len(result) == 2
