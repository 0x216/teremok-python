"""Photo bot - shows download mocking and outgoing-file assertions.

Tests: tests/examples/test_examples.py (test_photo_bot)
Run live: BOT_TOKEN=<token> python -m examples.photo_bot
"""

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


if __name__ == "__main__":
    import asyncio
    import os

    from aiogram import Bot, Dispatcher

    async def main() -> None:
        bot = Bot(os.environ["BOT_TOKEN"])
        dp = Dispatcher()
        dp.include_router(router)
        await dp.start_polling(bot)

    asyncio.run(main())
