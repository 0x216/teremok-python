"""teremok - black-box testing for aiogram 3.x bots. No network, no token."""

from .bot import DispatchResult, MockBot, Requests
from .builders import (
    DEFAULT_USER_ID,
    MockCallbackQuery,
    MockChat,
    MockMessageText,
    MockUpdate,
    MockUser,
)
from .responses import AutoResponder, CannotAutoRespond, classify
from .session import MockedSession, NoResultQueued

__all__ = [
    "AutoResponder",
    "CannotAutoRespond",
    "DEFAULT_USER_ID",
    "DispatchResult",
    "MockBot",
    "MockCallbackQuery",
    "MockChat",
    "MockMessageText",
    "MockedSession",
    "MockUpdate",
    "MockUser",
    "NoResultQueued",
    "Requests",
    "classify",
]
__version__ = "0.1.0"
