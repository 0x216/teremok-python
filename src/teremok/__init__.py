"""teremok - black-box testing for aiogram 3.x bots. No network, no token."""

from .responses import AutoResponder, CannotAutoRespond, classify
from .session import MockedSession, NoResultQueued

__all__ = [
    "AutoResponder",
    "CannotAutoRespond",
    "MockedSession",
    "NoResultQueued",
    "classify",
]
__version__ = "0.1.0"
