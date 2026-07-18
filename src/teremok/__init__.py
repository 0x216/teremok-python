"""teremok - black-box testing for aiogram 3.x bots. No network, no token."""

from .bot import CallbackNotAnswered, DispatchResult, MockBot, Requests
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
from .storage import fake_redis_storage
from .validation import ApiRuleViolation

__all__ = [
    "ApiRuleViolation",
    "AutoResponder",
    "CallbackNotAnswered",
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
    "fake_redis_storage",
]
__version__ = "0.3.0"
