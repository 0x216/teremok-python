"""Photo bot - shows download mocking and outgoing-file assertions."""

from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, Message

router = Router()


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    content = await bot.download(message.photo[-1].file_id)
    assert content is not None
    data = content.read()
    await message.answer(f"Got your photo: {len(data)} bytes")
    await message.answer_photo(
        BufferedInputFile(data, filename="echo.jpg"), caption="Right back at you!"
    )
