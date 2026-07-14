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
