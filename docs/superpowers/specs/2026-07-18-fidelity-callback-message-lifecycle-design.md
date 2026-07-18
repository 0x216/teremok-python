# Fidelity: callback-answer discipline, message lifecycle, Redis storage — Design Spec

**Date:** 2026-07-18
**Status:** Implemented (v0.3.0); §5 (concurrent driving) deferred to a follow-up issue

## Why

teremok's core promise is "test green ⇒ works in production". Two bug *classes*
slipped a green MockBot suite and only showed up on a live bot:

1. **Eternal spinner.** A callback handler returns without `callback.answer()`.
   Real Telegram keeps a loading spinner on the button for ~30s; MockBot
   auto-acks every callback, so the test never notices.
2. **"Screen out of date" / menu freshness.** Handlers that gate on
   `callback.message.message_id == stored_menu_id` (delete-and-resend menus)
   have a stale branch that a mock which mints a fresh carrier message id on
   every tap can never reach — and one that returns a *new* id from an edit
   (Telegram keeps the id) mismodels the stored id itself.

Both are pure, verifiable fidelity gaps, exactly the kind v0.2.0's validation
layer set out to close.

## What shipped

### 1. Callback-answer discipline (`strict_answer`, opt-in)

- `MockedSession` tracks `answered_callbacks: set[str]` (a query id stays
  answered forever, like Telegram). Recording is unconditional so per-step
  assertions work with the flag off.
- With `strict_answer=True`: a **second** `AnswerCallbackQuery` for the same id
  is routed through `check_response` as a genuine `TelegramBadRequest`
  (`query is too old ... or query ID is invalid`) — the same path validation
  uses.
- `MockBot.dispatch` records `callback_query_id` + `answered` on
  `DispatchResult`; with `strict_answer=True` a **handled** callback that was
  never answered raises `CallbackNotAnswered`. Unhandled callbacks (no handler
  ran) and non-callback updates are left alone.
- `DispatchResult.assert_answered()` gives the same check per-step without
  global strictness.
- **Opt-in**, default off: the answer-once error is stateful and a default-on
  flip would fail existing suites that legitimately dispatch un-answered
  callbacks. A future major version may reconsider the default. The escape
  hatch is simply not passing the flag.

### 2. Message-id + edit + stale lifecycle

- `AutoResponder.make_message` takes `message_id`; the `EditMessage*` family
  reuses `method.message_id` so an edit keeps its id, and an inline-message edit
  (`inline_message_id`, no chat message) returns `True`.
- `MockedSession.sent_messages` records every returned `Message` in call order;
  `MockBot.sent_messages` / `last_message` expose it. A test grabs an earlier
  entry and passes it as `MockCallbackQuery(message=..., data=...)` to tap a
  button on a now-stale screen.

### 3a. Redis-backed FSM storage (`fake_redis_storage()`, optional extra)

- `teremok.fake_redis_storage()` returns a real aiogram `RedisStorage` over
  in-process fakeredis — same JSON serialization and key builder as prod.
- `MockBot(*routers, storage=...)` accepts it (rejected alongside a
  ready-made `Dispatcher`, which already owns its storage).
- Gated behind the `redis` extra; the helper raises a clear `ImportError`
  pointing at `pip install teremok[redis]` when fakeredis is absent.

## 5. Deferred: concurrent-update driving (3b)

**Goal.** Feed two updates as concurrent tasks (aiogram's `handle_as_tasks=True`
shape) to surface double-tap / double-submit races.

**Why deferred.** `MockBot.dispatch` attributes captured requests to a step by
slicing `mock_session.requests[start:]`. Under true concurrency those slices
interleave, so per-step attribution is unreliable without tagging each outgoing
call with the update that caused it. Doing that faithfully needs a `contextvar`
set at `feed_update` entry and read in `MockedSession.make_request` — a
cross-cutting change worth its own PR and its own tests, rather than a
half-baked `gather()` that returns mis-sliced results.

**Sketch for the follow-up.**

- Set a `ContextVar[str]` (the update id) in a thin `dispatch` wrapper before
  `feed_update`; aiogram propagates contextvars into handler tasks.
- In `make_request`, stamp each captured method with the current update id.
- `MockBot.dispatch_as_tasks(*objs)` → `asyncio.gather` the dispatches and split
  captured requests by the stamp, returning one `DispatchResult` per update.
- Tests: two taps on the same "confirm" button racing → assert exactly one
  order/charge (the race the deterministic path can't show).

Tracked as a GitHub issue; interim workaround is to drive updates sequentially.

## Testing / compatibility bar

Same bar as prior releases: TDD per behaviour (`tests/test_callback_answer.py`,
`tests/test_message_lifecycle.py`, `tests/test_redis_storage.py`), ruff + mypy
strict clean on `src`, coverage ≥90%, existing public API and tests unchanged.
All new options are keyword-only and default to prior behaviour.
