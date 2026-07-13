from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator
from typing import Any, cast

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType

from .responses import AutoResponder


class NoResultQueued(AssertionError):
    """Raised in strict mode when an API call has no queued result."""


class MockedSession(BaseSession):
    """In-process replacement for aiogram's network session.

    Captures every outgoing API call as a typed TelegramMethod object and
    answers it from that method's queued-results FIFO, falling back to the
    auto-responder (unless strict=True).
    """

    def __init__(self, strict: bool = False) -> None:
        super().__init__()
        self.strict = strict
        self.requests: list[TelegramMethod[Any]] = []
        self.files: dict[str, tuple[str, bytes]] = {}
        self._results: dict[type[TelegramMethod[Any]], deque[Response[Any]]] = {}
        self.auto: AutoResponder = AutoResponder()

    def add_result(self, method: type[TelegramMethod[Any]], response: Response[Any]) -> None:
        self._results.setdefault(method, deque()).append(response)

    async def close(self) -> None:
        pass

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.requests.append(method)
        queue = self._results.get(type(method))
        if queue:
            response = queue.popleft()
            if not queue:
                del self._results[type(method)]
        else:
            if self.strict:
                raise NoResultQueued(
                    f"No result queued for {type(method).__name__} (strict mode); "
                    f"queue one with add_result({type(method).__name__}, ...)"
                )
            result = self.auto.respond(bot, method, files=self.files)
            response = Response[method.__returning__](  # type: ignore[name-defined]
                ok=True, result=result
            )
        checked = self.check_response(
            bot=bot,
            method=method,
            status_code=response.error_code or (200 if response.ok else 400),
            content=response.model_dump_json(),
        )
        return cast(TelegramType, checked.result)

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        # Telegram file URLs look like {base}/file/bot{token}/{file_path}
        # (TelegramAPIServer.file_url); extract the exact file_path rather
        # than suffix-matching, which confuses paths like "shared/name.jpg"
        # and "other/shared/name.jpg".
        marker = "/file/bot"
        requested_path = None
        if marker in url:
            tail = url.split(marker, 1)[1]
            _, _, requested_path = tail.partition("/")
        if requested_path:
            for registered_path, data in self.files.values():
                if registered_path == requested_path:
                    yield data
                    return
        yield b""
