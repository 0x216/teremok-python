"""Echo bot - the smallest possible teremok-testable router.

Tests: tests/examples/test_examples.py (test_echo_bot)
Run live: BOT_TOKEN=<token> python -m examples.echo_bot
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Hi! Send me anything and I'll echo it.")


@router.message()
async def echo(message: Message) -> None:
    await message.answer(message.text or "that wasn't text")


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
