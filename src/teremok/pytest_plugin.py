"""pytest plugin: auto-registered via the `pytest11` entry point on install."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aiogram import Dispatcher, Router

from .bot import MockBot

MockBotFactory = Callable[..., MockBot]


@pytest.fixture
def mock_bot() -> MockBotFactory:
    """Factory fixture: `bot = mock_bot(router1, router2)` or
    `bot = mock_bot(dispatcher, strict=True)` - pass any number of Routers,
    or a single Dispatcher, plus MockBot's keyword-only options."""

    def factory(*targets: Dispatcher | Router, **kwargs: Any) -> MockBot:
        return MockBot(*targets, **kwargs)

    return factory
