# teremok

[![PyPI](https://img.shields.io/pypi/v/teremok)](https://pypi.org/project/teremok/) ![Python](https://img.shields.io/pypi/pyversions/teremok) [![CI](https://github.com/0x216/teremok-python/actions/workflows/ci.yml/badge.svg)](https://github.com/0x216/teremok-python/actions/workflows/ci.yml)

Black-box testing for [aiogram 3.x](https://github.com/aiogram/aiogram) Telegram
bots. No network, no token, no mock servers - each test runs in milliseconds.

Inspired by Rust's [teremock](https://github.com/zerosixty/teremock): send mock
updates through your real dispatcher, then assert on what the bot sent back.
Named after the folk tale about a little house whose guests arrive one by one -
just like updates entering your bot.

## Install

```
pip install teremok
```

## Test setup

```
pip install teremok pytest-asyncio
```

teremok's tests (and the `mock_bot` fixture) are `async def`. Without
`pytest-asyncio` configured, async tests fail to run - add
this to your `pyproject.toml` (or the equivalent in `pytest.ini`):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

The quickstart below depends on this setting.

## Quickstart

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from teremok import MockBot, MockMessageText

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Hello!")

async def test_start(mock_bot):          # `mock_bot` fixture ships with the package
    bot = mock_bot(router)
    result = await bot.dispatch(MockMessageText("/start"))
    assert result.handled
    assert bot.requests.send_message[0].text == "Hello!"
```

Captures are **typed aiogram objects**, not JSON: `bot.requests.send_message`
returns `SendMessage` instances, `bot.requests.send_photo[0].photo` is the
actual `InputFile` your handler passed.

## FSM and multi-step conversations

```python
bot = mock_bot(form_router)
await bot.dispatch(MockMessageText("/form"))
await bot.dispatch(MockMessageText("Alice"))
await bot.dispatch(MockMessageText("30"))
assert bot.requests.send_message[-1].text == "Nice to meet you, Alice (30)!"
assert await bot.get_state() is None

# Or jump straight into the middle of a flow:
await bot.set_state(Form.age)
await bot.set_data({"name": "Bob"})
```

## Files and media

```python
bot.add_file("photo_1", b"...jpeg bytes...")     # bot.download() returns this
await bot.dispatch(MockMessagePhoto(file_id="photo_1", caption="lunch"))
assert bot.requests.send_photo[0].photo.filename == "echo.jpg"
```

## Custom API results and errors

```python
from aiogram.methods import SendMessage

bot.add_result(SendMessage, ok=False, error_code=400,
               description="Bad Request: chat not found")
# strict mode: MockBot(router, strict=True) fails on any un-queued call
```

Results are keyed by method type: queuing a `SendMessage` result never answers an
`AnswerCallbackQuery` (or any other method) call that happens to run first - every
other call keeps auto-responding.

## Strict API rules (v0.2.0)

Every outgoing call is checked against documented Bot API rules before it
gets a response: text/caption length limits, HTML/MarkdownV2/legacy-Markdown
well-formedness, entity offset bounds, and inline keyboard button shape
(exactly one action field, `callback_data` ≤64 bytes). A violation raises a
genuine `TelegramBadRequest` - same description text, same `check_response`
route as a real rejection, nothing new to catch. Escape hatch for tests that
intentionally send malformed payloads: `MockBot(router, validate=False)`.
Validation runs before queued results are consulted, so a call that fails
validation never consumes a queued result.
Full rule-by-rule reference, including what's deliberately not enforced, in
[docs/validation.md](docs/validation.md).

## Callback-answer discipline (v0.3.0)

Real Telegram shows an **endless loading spinner** on an inline button whose
callback query the bot never answers, and returns a 400 if you answer the same
query twice. MockBot auto-acks every callback with no once-tracking, so both
bugs sail through a green test. Opt in with one flag:

```python
bot = mock_bot(router, strict_answer=True)

# A handler that edits the screen but forgets callback.answer() now FAILS the
# step with CallbackNotAnswered - the eternal-spinner bug, caught in the test.
await bot.dispatch(MockCallbackQuery(data="open_menu"))

# Answering twice raises the same TelegramBadRequest the live API does.
```

Or assert a single step without making the whole session strict:

```python
result = await bot.dispatch(MockCallbackQuery(data="open_menu"))
result.assert_answered()          # fails unless the handler answered
assert result.answered            # also exposed as a bool
```

`strict_answer` is **opt-in** (default off) so existing suites that dispatch
un-answered callbacks stay green; turn it on to catch the class.

## Message-id, edits, and stale menus (v0.3.0)

An edit **keeps** its `message_id` (like Telegram), a fresh send gets a new one,
and every message the bot sends or edits is recorded in order:

```python
await bot.dispatch(MockMessageText("/menu"))
menu = bot.sent_messages[-1]              # the message the buttons are on

# Tap on the current screen -> the bot moves on to a new message (new id):
await bot.dispatch(MockCallbackQuery(data="nav", message=menu))

# Tap a button on the NOW-STALE earlier message -> the handler's
# "screen out of date" branch, unreachable with a fresh-every-time carrier:
await bot.dispatch(MockCallbackQuery(data="nav", message=menu))
```

## Redis-backed FSM storage for tests (v0.3.0)

`MemoryStorage` keeps FSM data as live Python objects, so a handler can stash a
value production's `RedisStorage` would refuse to JSON-serialize and the test
still passes. `fake_redis_storage()` runs a real aiogram `RedisStorage` over an
in-process [fakeredis](https://github.com/cunla/fakeredis-py) - same
serialization and key builder as prod, no server:

```
pip install teremok[redis]
```

```python
from teremok import fake_redis_storage

bot = mock_bot(router, storage=fake_redis_storage())
```

## What's covered

Every Bot API method is **captured** (interception happens below all methods, at
aiogram's session seam). Auto-response fidelity per method is tracked honestly in
[docs/coverage.md](docs/coverage.md); known edge cases live in
[docs/quirks.md](docs/quirks.md).

CI's freshness gate regenerates that table against the latest aiogram release on
every run, so a new aiogram release can turn CI red until someone regenerates and
commits the table - that's expected behavior, not a teremok bug.

## Examples

Four runnable bots with full test suites — the tests are the best
documentation of how to use teremok. Start with the
[examples guide](examples/README.md); the showcase is the
[pizza order wizard](examples/pizza_order_bot.py) (inline-keyboard toggles,
FSM, gettext i18n) and its [18 tests](tests/examples/test_pizza_order_bot.py).
Every example also runs live: `BOT_TOKEN=... python -m examples.pizza_order_bot`.

## Releasing (maintainers)

Tag `vX.Y.Z` and push - GitHub Actions builds and publishes via PyPI Trusted
Publishing (configure once in PyPI project settings).

## Credits

The name and the whole idea are borrowed with love from
[teremock](https://github.com/zerosixty/teremock) by
[@zerosixty](https://github.com/zerosixty) — a Rust testing library for
teloxide bots (MIT). teremok is its independent aiogram counterpart: no code
is shared (different language, different framework), but the black-box testing
philosophy — and the pun — are theirs. Related prior art:
[teloxide_tests](https://docs.rs/teloxide_tests).

## License

MIT
