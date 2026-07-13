"""teremok - black-box testing for aiogram 3.x bots. No network, no token."""

from .session import MockedSession, NoResultQueued

__all__ = ["MockedSession", "NoResultQueued"]
__version__ = "0.1.0"
