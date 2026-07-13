# teremok — Design Spec

**Date:** 2026-07-13
**Status:** Approved pending user review

## What

`teremok` is an open-source Python library for testing [aiogram 3.x](https://github.com/aiogram/aiogram) Telegram bots without network access, API tokens, or external services. It is the aiogram counterpart of Rust's [teremock](https://github.com/zerosixty/teremock) / [teloxide_tests](https://docs.rs/teloxide_tests): black-box testing — send mock updates through the real dispatcher, then assert on the bot's outgoing API calls and FSM state.

The name: "Теремок" is the Russian folk tale about a little house that characters enter one by one — like updates entering a bot. It is also a nod to teremock. The PyPI name `teremok` is free (verified 2026-07-13).

## Why not a Rust mock server

teremock keeps an HTTP mock server because teloxide is hard-wired to reqwest. aiogram exposes `BaseSession` as a clean seam, so we intercept in-process with zero HTTP — faster than any localhost server and trivially installable (`pip install teremok`, no wheels/binaries). An HTTP-level mode can be added later without changing the public API; it is out of scope for v1.

## Audience and scope

Open source on PyPI, for the aiogram community. v1 includes:

- Core: text messages, commands, callback queries, typed assertions on responses
- FSM: seed state/data before dispatch, assert state/data after
- Multi-step conversations in one test (state persists across dispatches)
- Media: incoming photo/document/voice updates; assertions on outgoing `InputFile`; mocked `get_file`/`download`
- pytest plugin with ready fixtures (auto-registered entry point)

Out of scope for v1: inline mode, payments, business connections, web apps, aiogram-dialog integration (tracked as roadmap items in the coverage table, not silently missing).

## Architecture

Three layers plus a pytest plugin, all pure Python:

### 1. `MockedSession(BaseSession)` — the interception point

Every aiogram API call arrives here as a **typed** `TelegramMethod` object (`SendMessage`, `SendPhoto`, `AnswerCallbackQuery`, …). The session:

- records the method object into the capture journal (all methods are captured — interception is generic, so capture coverage is 100% of the Bot API surface aiogram supports);
- returns a response: a user-registered result if one was queued (`add_result`), otherwise an auto-generated plausible result (e.g. `SendMessage` → `Message` with per-chat auto-incrementing `message_id`, echoing the request fields);
- in `strict=True` mode, raises on any call that has no queued result.

### 2. `MockBot` — the facade

Wraps a real `Bot(token="42:TEST", session=MockedSession)` plus the user's `Dispatcher` (or bare `Router`s, from which it builds a dispatcher with `MemoryStorage`).

```python
bot = MockBot(dp)                      # or MockBot(router1, router2)
result = await bot.dispatch(MockMessageText("/start"))

sent = bot.requests.send_message[0]    # typed SendMessage object
assert sent.text == "Привет!"
assert result.handled                  # a handler actually ran
```

API:

- `await bot.dispatch(update)` → `DispatchResult` with `.handled: bool` and `.requests` (the slice captured during this dispatch). Full journal stays on `bot.requests`.
- `bot.requests.<method_snake_case>` → typed list per method; `bot.requests.all` → everything in order.
- `bot.add_result(method_type_or_matcher, result_or_exception)` — queue custom API responses, including `TelegramAPIError`s to test error paths.
- `bot.add_file(file_id, data: bytes)` — makes `bot.get_file()`/`bot.download()` inside handlers return these bytes (needed by bots that download user photos).
- FSM helpers: `bot.set_state(...)`, `bot.get_state()`, `bot.set_data(...)`, `bot.get_data()` — operate on the dispatcher's storage with a correctly built `StorageKey` (defaults to the default mock user/chat, overridable).

Multi-step conversations = several `dispatch()` calls on one `MockBot`; storage persists between them.

### 3. Builders

`MockMessageText`, `MockMessagePhoto`, `MockMessageDocument`, `MockMessageVoice`, `MockCallbackQuery`, `MockUser`, `MockChat`, `MockUpdate` (escape hatch for raw updates). Sensible defaults (user id 12345, private chat), everything overridable via kwargs. Builders produce real aiogram types (`Update`), so anything they miss can be built by hand with aiogram itself — the library never blocks the user.

### 4. pytest plugin

Entry point `teremok`, giving a `mock_bot` factory fixture out of the box:

```python
async def test_start(mock_bot):
    bot = mock_bot(dp)
    ...
```

Works with `pytest-asyncio`; no conftest boilerplate.

## Data flow

Builder → `Update` → `dp.feed_update(bot, update)` → user handlers run → API calls hit `MockedSession` → captured + auto-response → test asserts on captures and FSM state.

## Error handling

- Handler exceptions propagate to the test unchanged (never swallowed).
- Unknown/unqueued API call: auto-response by default; `strict=True` raises.
- `dispatch()` on an update no handler matches: returns `handled=False` (not an error) so tests can assert both positives and negatives.

## Quality requirements (open-source bar)

This is a public library, not a personal tool. Two hard requirements:

### Coverage table (public, auto-generated, CI-enforced)

`docs/coverage.md` lists **every** update type and **every** Telegram Bot API method known to the installed aiogram version, with status:

- ✅ **Curated** — dedicated realistic auto-response and tests
- 🟡 **Generic** — captured and answered with a generic auto-response (works, less realistic)
- 📋 **Planned** — known gap with an issue link (e.g. inline mode in v1)

The table is generated by a script that introspects `aiogram.methods` / `aiogram.types`, so it can never silently drift: CI regenerates it and fails if the committed version is stale. Because interception is at the session seam, *capture* works for 100% of methods automatically; the table tracks the fidelity of auto-responses and builder coverage honestly.

### Known-quirks discipline

Every discovered edge case ("косяк") gets: a regression test + an entry in `docs/quirks.md` (what, why, workaround if not fixed). Candidate quirks already known at design time, to be handled in v1:

- per-chat (not global) `message_id` counters;
- `callback_query.answer()` must be captured like any call and not require a queued result;
- `message_thread_id` / topics passthrough;
- media groups (album = several updates sharing `media_group_id`);
- `edited_message` vs `message` update types;
- FSM `StorageKey` must include `bot.id` exactly as aiogram builds it, or state helpers silently miss;
- `InputFile` variants (`BufferedInputFile`, `FSInputFile`, `URLInputFile`) must all be assertable.

### Test/CI bar

- pytest + pytest-asyncio, coverage gate ≥ 90% on `src/teremok/` (pytest-cov), badge in README.
- CI matrix: Python 3.10–3.13 × aiogram (oldest supported 3.4 → latest release, plus `dev-3.x` as allowed-failure early warning).
- Dogfood examples under `examples/` (echo bot, FSM form, photo bot) that run as tests and double as documentation.
- ruff + mypy (strict on `src/`).

## Compatibility risk

`BaseSession` is a semi-internal aiogram API. Mitigation: the CI matrix above, pinning `aiogram>=3.4,<4` in package metadata, and the fact that aiogram's own test suite uses the same seam (breakage would be loud and rare).

## Repository layout

```
teremok/
├─ src/teremok/
│  ├─ session.py        # MockedSession
│  ├─ bot.py            # MockBot, DispatchResult, capture journal
│  ├─ builders.py       # Mock* builders
│  ├─ fsm.py            # FSM helpers
│  ├─ files.py          # add_file / download mocking
│  └─ pytest_plugin.py
├─ tests/
├─ examples/            # dogfood bots, run in CI
├─ docs/
│  ├─ coverage.md       # auto-generated API coverage table
│  └─ quirks.md         # known edge cases and their status
├─ scripts/gen_coverage.py
├─ README.md            # English, examples-first
└─ .github/workflows/   # lint+type+test matrix, coverage-table freshness, PyPI publish on tag
```

## Success criteria

- A realistic bot (FoodBot-class: photos, FSM, multi-step) can be tested with no network and no token, each test in milliseconds.
- `pip install teremok` → first green test within 5 minutes using only the README.
- Coverage table published and CI-fresh; every known quirk has a test or a documented workaround.
