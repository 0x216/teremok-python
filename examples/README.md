# teremok examples

Each example is a real, runnable aiogram bot **and** has a full test suite
written with teremok. The bots live here; their tests live in
[`tests/examples/`](../tests/examples/) — read them side by side, the tests
are the actual documentation of how to use teremok.

| Example | What it demonstrates | Tests |
|---|---|---|
| [`echo_bot.py`](echo_bot.py) | The smallest testable router: commands, text replies | [`test_examples.py`](../tests/examples/test_examples.py) → `test_echo_bot` |
| [`fsm_form_bot.py`](fsm_form_bot.py) | FSM states, multi-step conversations, asserting state | [`test_examples.py`](../tests/examples/test_examples.py) → `test_fsm_form_bot_full_flow` |
| [`photo_bot.py`](photo_bot.py) | Incoming photos, `bot.download()` mocking, outgoing `InputFile` assertions | [`test_examples.py`](../tests/examples/test_examples.py) → `test_photo_bot` |
| [`pizza_order_bot.py`](pizza_order_bot.py) | The full arsenal: CallbackData routing, live keyboard toggles (`edit_message_reply_markup`), mixed callback/text input, validation branches, gettext i18n through real middleware | [`test_pizza_order_bot.py`](../tests/examples/test_pizza_order_bot.py) (18 tests) |

## Run the tests (no token, no network)

```bash
git clone https://github.com/0x216/teremok-python
cd teremok-python
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest tests/examples/ -v
```

Every test runs in milliseconds against `MockBot` — no Telegram account
involved. This is exactly how you'd test your own bot; start by copying the
pattern from `test_pizza_order_bot.py`:

```python
from teremok import MockBot, MockMessageText, MockCallbackQuery

async def test_start():
    bot = MockBot(create_router())              # your Dispatcher or Router(s)
    await bot.dispatch(MockMessageText("/order"))
    assert bot.requests.send_message[0].text == "Choose your language:"
```

## Run a bot live (against real Telegram)

Each example is also a working bot. Get a token from
[@BotFather](https://t.me/BotFather) and:

```bash
# Linux/macOS
BOT_TOKEN=123456:ABC... python -m examples.pizza_order_bot
```

```powershell
# Windows
$env:BOT_TOKEN = "123456:ABC..."; python -m examples.pizza_order_bot
```

Then open your bot in Telegram and send `/order` (pizza), `/start` (echo),
`/form` (FSM form), or a photo (photo bot).

Note on the pizza bot's translations: the Russian catalog is committed as a
readable `.po` file; the binary `.mo` that gettext loads is compiled
automatically at import time (needs Babel, which `pip install -e .[dev]`
brings in). Without Babel the bot still works — it just falls back to the
English strings.
