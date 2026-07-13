from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator
from typing import Any, cast

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType


class NoResultQueued(AssertionError):
    """Raised in strict mode when an API call has no queued result."""


class _RaisingAutoResponder:
    """Placeholder until the real AutoResponder lands; always refuses."""

    def respond(
        self, bot: Bot, method: TelegramMethod[Any], files: dict[str, tuple[str, bytes]]
    ) -> Any:
        raise NoResultQueued(
            f"No result queued for {type(method).__name__} and no auto-responder available"
        )


class MockedSession(BaseSession):
    """In-process replacement for aiogram's network session.

    Captures every outgoing API call as a typed TelegramMethod object and
    answers it from the queued-results FIFO, falling back to the
    auto-responder (unless strict=True).
    """

    def __init__(self, strict: bool = False) -> None:
        super().__init__()
        self.strict = strict
        self.requests: list[TelegramMethod[Any]] = []
        self.files: dict[str, tuple[str, bytes]] = {}
        self._results: deque[Response[Any]] = deque()
        self.auto: Any = _RaisingAutoResponder()

    def add_result(self, response: Response[Any]) -> None:
        self._results.append(response)

    async def close(self) -> None:
        pass

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.requests.append(method)
        if self._results:
            response = self._results.popleft()
            if response.ok:
                return cast(TelegramType, response.result)
            self.check_response(
                bot=bot,
                method=method,
                status_code=response.error_code or 400,
                content=response.model_dump_json(),
            )
            raise RuntimeError("check_response must raise for not-ok responses")
        if self.strict:
            raise NoResultQueued(
                f"No result queued for {type(method).__name__} (strict mode); "
                f"queue one with bot.add_result(...)"
            )
        return cast(TelegramType, self.auto.respond(bot, method, files=self.files))

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        for file_path, data in self.files.values():
            if url.endswith(file_path):
                yield data
                return
        yield b""
