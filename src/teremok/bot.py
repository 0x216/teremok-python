from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiogram.methods as _methods_module
from aiogram import Bot, Dispatcher, Router
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response
from aiogram.types import CallbackQuery, Message, Update, User

from .builders import DEFAULT_USER_ID, next_update_id
from .session import MockedSession


class Requests:
    """Typed access to captured API calls: requests.send_message -> [SendMessage, ...]."""

    def __init__(self, items: list[TelegramMethod[Any]]):
        self.all = items

    def __getattr__(self, name: str) -> list[TelegramMethod[Any]]:
        camel = "".join(part.capitalize() for part in name.split("_"))
        method_cls = getattr(_methods_module, camel, None)
        if (
            method_cls is None
            or not isinstance(method_cls, type)
            or not issubclass(method_cls, TelegramMethod)
            or method_cls is TelegramMethod
        ):
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

    def add_file(self, file_id: str, data: bytes, file_path: str | None = None) -> None:
        """Register file content so handlers can bot.get_file()/bot.download() it."""
        self.mock_session.files[file_id] = (file_path or f"files/{file_id}.dat", data)

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

    def fsm(self, user_id: int = DEFAULT_USER_ID, chat_id: int | None = None) -> FSMContext:
        """FSMContext for the given user/chat, keyed exactly like aiogram does.

        The key includes this bot's id - a mismatch there makes state helpers
        silently target a different bucket than dispatch (see docs/quirks.md).
        """
        resolved_chat = chat_id if chat_id is not None else user_id
        return FSMContext(
            storage=self.dp.storage,
            key=StorageKey(bot_id=self.id, chat_id=resolved_chat, user_id=user_id),
        )

    async def set_state(
        self, state: Any, user_id: int = DEFAULT_USER_ID, chat_id: int | None = None
    ) -> None:
        await self.fsm(user_id, chat_id).set_state(state)

    async def get_state(
        self, user_id: int = DEFAULT_USER_ID, chat_id: int | None = None
    ) -> str | None:
        return await self.fsm(user_id, chat_id).get_state()

    async def set_data(
        self,
        data: dict[str, Any],
        user_id: int = DEFAULT_USER_ID,
        chat_id: int | None = None,
    ) -> None:
        await self.fsm(user_id, chat_id).set_data(data)

    async def get_data(
        self, user_id: int = DEFAULT_USER_ID, chat_id: int | None = None
    ) -> dict[str, Any]:
        return await self.fsm(user_id, chat_id).get_data()
