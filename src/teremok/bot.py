from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiogram.methods as _methods_module
from aiogram import Bot, Dispatcher, Router
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response
from aiogram.types import CallbackQuery, Message, Update, User

from .builders import next_update_id
from .session import MockedSession


class Requests:
    """Typed access to captured API calls: requests.send_message -> [SendMessage, ...]."""

    def __init__(self, items: list[TelegramMethod[Any]]):
        self.all = items

    def __getattr__(self, name: str) -> list[TelegramMethod[Any]]:
        camel = "".join(part.capitalize() for part in name.split("_"))
        if not hasattr(_methods_module, camel):
            raise AttributeError(
                f"Unknown Telegram method {name!r} (no aiogram.methods.{camel})"
            )
        return [m for m in self.all if type(m).__name__ == camel]

    def __len__(self) -> int:
        return len(self.all)


@dataclass
class DispatchResult:
    handled: bool
    requests: Requests
    result: Any


def _as_update(obj: Update | Message | CallbackQuery) -> Update:
    if isinstance(obj, Update):
        return obj
    if isinstance(obj, Message):
        return Update(update_id=next_update_id(), message=obj)
    if isinstance(obj, CallbackQuery):
        return Update(update_id=next_update_id(), callback_query=obj)
    raise TypeError(
        f"Cannot dispatch {type(obj).__name__}; pass an Update, Message, or CallbackQuery"
    )


class MockBot(Bot):
    """A real aiogram Bot wired to MockedSession plus the user's dispatcher."""

    def __init__(
        self,
        *targets: Dispatcher | Router,
        token: str = "42:TEST",
        strict: bool = False,
        **bot_kwargs: Any,
    ) -> None:
        session = MockedSession(strict=strict)
        super().__init__(token, session=session, **bot_kwargs)
        self.mock_session: MockedSession = session
        self._me = User(id=self.id, is_bot=True, first_name="TestBot", username="test_bot")
        if len(targets) == 1 and isinstance(targets[0], Dispatcher):
            self.dp: Dispatcher = targets[0]
        else:
            self.dp = Dispatcher()
            for target in targets:
                if isinstance(target, Dispatcher):
                    raise TypeError("Pass either one Dispatcher or any number of Routers")
                self.dp.include_router(target)
        self.last: DispatchResult | None = None

    @property
    def requests(self) -> Requests:
        return Requests(self.mock_session.requests)

    async def dispatch(
        self, obj: Update | Message | CallbackQuery, **kwargs: Any
    ) -> DispatchResult:
        update = _as_update(obj)
        start = len(self.mock_session.requests)
        result = await self.dp.feed_update(self, update, **kwargs)
        captured = self.mock_session.requests[start:]
        self.last = DispatchResult(
            handled=result is not UNHANDLED, requests=Requests(captured), result=result
        )
        return self.last

    def add_result(
        self,
        method: type[TelegramMethod[Any]],
        result: Any = None,
        *,
        ok: bool = True,
        error_code: int | None = None,
        description: str | None = None,
    ) -> None:
        if error_code is None:
            error_code = 200 if ok else 400
        response = Response[method.__returning__](  # type: ignore[name-defined]
            ok=ok, result=result, error_code=error_code, description=description
        )
        self.mock_session.add_result(response)
