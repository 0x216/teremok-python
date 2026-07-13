"""Echo bot - the smallest possible teremok-testable router."""

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
