from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiogram.methods as _methods_module
from aiogram import Bot, Dispatcher, Router
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.methods import AnswerCallbackQuery, TelegramMethod
from aiogram.methods.base import Response
from aiogram.types import CallbackQuery, Message, Update, User

from .builders import DEFAULT_USER_ID, next_update_id
from .session import MockedSession


class CallbackNotAnswered(AssertionError):
    """Raised in strict-answer mode when a handled callback_query is never
    answered (the user would see an endless loading spinner on the button)."""


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
    # Set when the dispatched update carried a callback_query: its id, and
    # whether the handler answered it (called callback.answer()) during this
    # dispatch. `answered` stays False for non-callback updates.
    callback_query_id: str | None = None
    answered: bool = False

    def assert_answered(self) -> None:
        """Fail unless this dispatch's callback_query was answered.

        Usable regardless of strict_answer, so a single step can be asserted
        without making the whole session strict. A no-op-worthy dispatch that
        carried no callback_query is a usage error and also fails.
        """
        if self.callback_query_id is None:
            raise AssertionError(
                "assert_answered() only applies to a dispatched callback_query"
            )
        if not self.answered:
            raise AssertionError(
                f"callback_query {self.callback_query_id!r} was handled but never "
                "answered (callback.answer() was not called) - in production the "
                "user would see an endless loading spinner on the tapped button"
            )


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
        validate: bool = True,
        strict_answer: bool = False,
        storage: BaseStorage | None = None,
        **bot_kwargs: Any,
    ) -> None:
        session = MockedSession(strict=strict, validate=validate, strict_answer=strict_answer)
        super().__init__(token, session=session, **bot_kwargs)
        self.mock_session: MockedSession = session
        self._me = User(id=self.id, is_bot=True, first_name="TestBot", username="test_bot")
        if len(targets) == 1 and isinstance(targets[0], Dispatcher):
            if storage is not None:
                raise TypeError(
                    "storage= applies only when passing Routers; a Dispatcher already "
                    "owns its storage"
                )
            self.dp: Dispatcher = targets[0]
        else:
            self.dp = Dispatcher(storage=storage) if storage is not None else Dispatcher()
            for target in targets:
                if isinstance(target, Dispatcher):
                    raise TypeError("Pass either one Dispatcher or any number of Routers")
                self.dp.include_router(target)
        self.last: DispatchResult | None = None

    @property
    def sent_messages(self) -> list[Message]:
        """Every Message this bot sent or edited, in call order - the on-screen
        history. An edit keeps its message_id, so re-editing appends another
        entry with the same id. Tap a button on an EARLIER entry to exercise a
        handler's stale-message ("screen out of date") branch."""
        return self.mock_session.sent_messages

    @property
    def last_message(self) -> Message | None:
        """The most recently sent/edited Message, or None if none yet."""
        msgs = self.mock_session.sent_messages
        return msgs[-1] if msgs else None

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
        cq_id = update.callback_query.id if update.callback_query is not None else None
        start = len(self.mock_session.requests)
        result = await self.dp.feed_update(self, update, **kwargs)
        captured = self.mock_session.requests[start:]
        handled = result is not UNHANDLED
        answered = cq_id is not None and any(
            isinstance(m, AnswerCallbackQuery) and m.callback_query_id == cq_id
            for m in captured
        )
        self.last = DispatchResult(
            handled=handled,
            requests=Requests(captured),
            result=result,
            callback_query_id=cq_id,
            answered=answered,
        )
        # strict-answer: a handled callback the handler returned from without
        # answering is the eternal-spinner bug - fail the step, like production.
        if self.mock_session.strict_answer and cq_id is not None and handled and not answered:
            raise CallbackNotAnswered(
                f"callback_query {cq_id!r} was handled but never answered "
                "(callback.answer() was not called) - in production the user would "
                "see an endless loading spinner on the tapped button. Answer it in "
                "the handler, or dispatch with strict_answer=False if this step "
                "intentionally leaves it open."
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
        self.mock_session.add_result(method, response)

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
