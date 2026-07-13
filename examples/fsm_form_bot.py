"""Two-question FSM form - shows multi-step conversation testing."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

router = Router()


class Form(StatesGroup):
    name = State()
    age = State()


@router.message(Command("form"))
async def start_form(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.name)
    await message.answer("What's your name?")


@router.message(Form.name)
async def form_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await state.set_state(Form.age)
    await message.answer("How old are you?")


@router.message(Form.age)
async def form_age(message: Message, state: FSMContext) -> None:
    data = await state.update_data(age=message.text)
    await state.clear()
    await message.answer(f"Nice to meet you, {data['name']} ({data['age']})!")
