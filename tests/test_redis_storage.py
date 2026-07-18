"""Redis-backed FSM storage for tests (v0.3.0, optional `redis` extra).

``MemoryStorage`` keeps FSM data as live Python objects, so a handler can stash
a value that production's ``RedisStorage`` would refuse to JSON-serialize - and
the test stays green. ``fake_redis_storage()`` runs the real aiogram
``RedisStorage`` over an in-process fakeredis, closing that gap without a server.
"""

from __future__ import annotations

import pytest
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

pytest.importorskip("fakeredis")

from teremok import MockBot, MockMessageText, fake_redis_storage  # noqa: E402


class Form(StatesGroup):
    name = State()


def _form_router() -> Router:
    router = Router()

    @router.message(Command("form"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.set_state(Form.name)
        await message.answer("name?")

    @router.message(Form.name)
    async def got_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name=message.text)
        await state.clear()
        await message.answer(f"hi {message.text}")

    return router


def _stash_router() -> Router:
    router = Router()

    @router.message(Command("stash"))
    async def stash(message: Message, state: FSMContext) -> None:
        # A set is a perfectly good live Python object but not JSON - prod's
        # RedisStorage rejects it; MemoryStorage swallows it silently.
        await state.update_data(tags={"a", "b"})
        await message.answer("stashed")

    return router


async def test_cross_message_state_persists_over_redis() -> None:
    bot = MockBot(_form_router(), storage=fake_redis_storage())
    await bot.dispatch(MockMessageText("/form"))
    assert await bot.get_state() == Form.name.state  # survived the storage round-trip
    await bot.dispatch(MockMessageText("Alice"))
    assert bot.requests.send_message[-1].text == "hi Alice"
    assert await bot.get_state() is None


async def test_redis_storage_rejects_non_json_data_like_prod() -> None:
    bot = MockBot(_stash_router(), storage=fake_redis_storage())
    with pytest.raises(TypeError):
        await bot.dispatch(MockMessageText("/stash"))


async def test_memory_storage_hides_the_non_json_bug() -> None:
    # Same handler, default MemoryStorage: the bug is invisible - which is
    # exactly why fake_redis_storage() exists.
    bot = MockBot(_stash_router())
    result = await bot.dispatch(MockMessageText("/stash"))
    assert result.handled
    assert bot.requests.send_message[-1].text == "stashed"


async def test_dispatcher_and_storage_are_mutually_exclusive() -> None:
    from aiogram import Dispatcher

    with pytest.raises(TypeError, match="storage="):
        MockBot(Dispatcher(), storage=fake_redis_storage())
