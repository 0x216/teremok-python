from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from teremok import MockBot, MockMessageText


class Form(StatesGroup):
    name = State()
    age = State()


def make_router() -> Router:
    router = Router()

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
        await message.answer(f"Done, {data['name']} ({data['age']})!")

    return router


async def test_full_multistep_conversation() -> None:
    bot = MockBot(make_router())
    await bot.dispatch(MockMessageText("/form"))
    await bot.dispatch(MockMessageText("Alice"))
    await bot.dispatch(MockMessageText("30"))
    texts = [m.text for m in bot.requests.send_message]
    assert texts == ["What's your name?", "How old are you?", "Done, Alice (30)!"]
    assert await bot.get_state() is None  # cleared at the end


async def test_seed_state_before_dispatch() -> None:
    bot = MockBot(make_router())
    await bot.set_state(Form.age)
    await bot.set_data({"name": "Bob"})
    result = await bot.dispatch(MockMessageText("42"))
    assert result.handled
    assert bot.requests.send_message[0].text == "Done, Bob (42)!"


async def test_assert_state_and_data_after_dispatch() -> None:
    bot = MockBot(make_router())
    await bot.dispatch(MockMessageText("/form"))
    await bot.dispatch(MockMessageText("Carol"))
    assert await bot.get_state() == Form.age.state
    assert (await bot.get_data())["name"] == "Carol"


async def test_states_are_isolated_per_user() -> None:
    from teremok import MockUser

    bot = MockBot(make_router())
    await bot.dispatch(MockMessageText("/form", user=MockUser(user_id=1)))
    assert await bot.get_state(user_id=1) == Form.name.state
    assert await bot.get_state(user_id=2) is None
