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
    """Factory fixture: `bot = mock_bot(router_or_dispatcher, strict=...)`."""

    def factory(*targets: Dispatcher | Router, **kwargs: Any) -> MockBot:
        return MockBot(*targets, **kwargs)

    return factory
