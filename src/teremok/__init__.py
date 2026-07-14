"""teremok - black-box testing for aiogram 3.x bots. No network, no token."""

from .bot import DispatchResult, MockBot, Requests
from .builders import (
    DEFAULT_USER_ID,
    MockCallbackQuery,
    MockChat,
    MockMessageDocument,
    MockMessagePhoto,
    MockMessageText,
    MockMessageVoice,
    MockUpdate,
    MockUser,
)
from .responses import AutoResponder, CannotAutoRespond, classify
from .session import MockedSession, NoResultQueued
from .validation import ApiRuleViolation

__all__ = [
    "ApiRuleViolation",
    "AutoResponder",
    "CannotAutoRespond",
    "DEFAULT_USER_ID",
    "DispatchResult",
    "MockBot",
    "MockCallbackQuery",
    "MockChat",
    "MockMessageDocument",
    "MockMessagePhoto",
    "MockMessageText",
    "MockMessageVoice",
    "MockedSession",
    "MockUpdate",
    "MockUser",
    "NoResultQueued",
    "Requests",
    "classify",
]
__version__ = "0.2.0"
