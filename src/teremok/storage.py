"""Redis-backed FSM storage for tests, without a real Redis server.

aiogram's ``MemoryStorage`` keeps FSM state and data as live Python objects, so
a handler can stash anything (a ``Decimal``, a ``set``, a domain object) and the
test stays green - yet production, backed by ``RedisStorage``, JSON-serializes
every value and would raise. It also hides key/serialization-format bugs that
only appear once state crosses a real storage boundary.

``fake_redis_storage()`` returns a real aiogram ``RedisStorage`` wired to an
in-process `fakeredis <https://github.com/cunla/fakeredis-py>`_ instance: same
serialization, same key builder, no server, no Docker. Pass it as
``MockBot(router, storage=fake_redis_storage())``.

Requires the optional ``redis`` extra: ``pip install teremok[redis]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiogram.fsm.storage.redis import RedisStorage


def fake_redis_storage(**redis_storage_kwargs: Any) -> RedisStorage:
    """A real aiogram ``RedisStorage`` backed by an in-process fakeredis.

    Extra keyword arguments are forwarded to ``RedisStorage`` (e.g.
    ``key_builder=``, ``state_ttl=``), so a test can mirror the exact storage
    configuration production uses.
    """
    try:
        from fakeredis.aioredis import FakeRedis
    except ImportError as exc:  # pragma: no cover - exercised via the error message
        raise ImportError(
            "fake_redis_storage() needs the optional 'redis' extra: "
            "pip install teremok[redis]"
        ) from exc
    from aiogram.fsm.storage.redis import RedisStorage

    return RedisStorage(redis=FakeRedis(), **redis_storage_kwargs)
