# Pizza order example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hard-dogfood example to teremok — a multi-step inline-keyboard pizza-order wizard with real gettext i18n — plus a full test suite, per the approved spec at `docs/superpowers/specs/2026-07-14-pizza-example-design.md`.

**Architecture:** One example module exposing `create_router()` (fresh Router per call — aiogram forbids re-attaching a Router, quirk #13), plain async handlers wired via explicit `register(...)`, `FSMI18nMiddleware` for locale-in-FSM i18n, one committed `ru` gettext catalog compiled to `.mo` on the fly by the tests' conftest.

**Tech Stack:** aiogram 3.x (`CallbackData`, `StatesGroup`, `aiogram.utils.i18n`), Babel (dev-only, po→mo compilation), teremok itself for the tests.

## Global Constraints

- Repo root: `C:\Users\ant\teremok`. Commands run with venv activated: `.venv\Scripts\Activate.ps1` (PowerShell). Python 3.14, aiogram 3.29.1 in the venv.
- Package dependency stays `aiogram>=3.4,<4` ONLY. Babel is added to the `dev` extra ONLY.
- Tests import only from `teremok` top level (+ `examples.pizza_order_bot`).
- `ruff check .` clean before each commit; `mypy src` untouched/clean (examples are outside mypy scope).
- Full suite green; coverage gate (`coverage run --source=teremok -m pytest` + `coverage report --fail-under=90`) unaffected — examples are outside `--source`.
- Stage files by name (never `git add -A`).
- All code/docs in English. `.mo` files are generated artifacts — git-ignored, never committed.
- CI must stay green on the aiogram==3.4.1 leg: use only i18n/CallbackData APIs that exist across 3.4→latest (`I18n`, `FSMI18nMiddleware`, `I18nMiddleware.setup(router)`, `CallbackData.filter()`, `.pack()`). If the installed aiogram's signature differs from the plan's code, adapt minimally and flag it in the report.

---

### Task 1: Example bot, ru locale, conftest compilation, deps

**Files:**
- Create: `examples/pizza_order_bot.py`
- Create: `examples/pizza_locales/ru/LC_MESSAGES/messages.po`
- Modify: `tests/examples/conftest.py` (append .mo compilation)
- Modify: `pyproject.toml` (babel in dev extras)
- Modify: `.gitignore` (`*.mo`)

**Interfaces:**
- Consumes: aiogram only.
- Produces (used by Task 2):
  - `create_router() -> Router` — fresh router with all handlers + i18n middleware attached
  - `class OrderStates(StatesGroup)` — `choosing_language`, `choosing_size`, `picking_toppings`, `entering_address`, `confirming`
  - CallbackData factories: `LangCb(code: str)` prefix `lang`; `SizeCb(size: str)` prefix `size`; `ToppingCb(name: str)` prefix `top`; `ActionCb(action: str)` prefix `act` (actions: `done`, `confirm`, `cancel`)
  - Constants: `SIZES = {"S": 8.0, "M": 10.0, "L": 12.0}`, `TOPPINGS = ("Cheese", "Mushrooms", "Pepperoni", "Olives")`, `TOPPING_PRICE = 1.5`, `MIN_ADDRESS_LEN = 5`
  - `total_price(size: str, toppings: list[str]) -> float`

- [ ] **Step 1: Add babel to dev extras and ignore .mo**

In `pyproject.toml` dev extras add `"babel>=2.13",` after the `"coverage>=7",` line. In `.gitignore` add a line `*.mo`.

- [ ] **Step 2: Write the ru catalog**

`examples/pizza_locales/ru/LC_MESSAGES/messages.po`:

```po
msgid ""
msgstr ""
"Project-Id-Version: pizza-order-bot\n"
"Language: ru\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

msgid "Choose your language:"
msgstr "Выбери язык:"

msgid "Choose your size:"
msgstr "Выбери размер:"

msgid "Pick your toppings:"
msgstr "Выбери топпинги:"

msgid "Done ➡️"
msgstr "Готово ➡️"

msgid "❌ Cancel"
msgstr "❌ Отмена"

msgid "Send me your delivery address:"
msgstr "Пришли адрес доставки:"

msgid "Address looks too short, try again:"
msgstr "Адрес слишком короткий, попробуй ещё раз:"

msgid ""
"Your order:\n"
"Size: {size}\n"
"Toppings: {toppings}\n"
"Address: {address}\n"
"Total: ${total}"
msgstr ""
"Твой заказ:\n"
"Размер: {size}\n"
"Топпинги: {toppings}\n"
"Адрес: {address}\n"
"Итого: ${total}"

msgid "Confirm ✅"
msgstr "Подтвердить ✅"

msgid "Order placed! Total: ${total}"
msgstr "Заказ оформлен! Итого: ${total}"

msgid "Order cancelled"
msgstr "Заказ отменён"

msgid "(none)"
msgstr "(без топпингов)"

msgid "Cheese"
msgstr "Сыр"

msgid "Mushrooms"
msgstr "Грибы"

msgid "Pepperoni"
msgstr "Пепперони"

msgid "Olives"
msgstr "Оливки"
```

Save as UTF-8.

- [ ] **Step 3: Extend tests/examples/conftest.py**

Append to the existing file (keep the sys.path block as is):

```python
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def _compile_locales() -> None:
    """Compile committed .po catalogs to .mo so I18n can load them.

    .mo files are binary and git-ignored; tests regenerate them on demand.
    Runs at conftest import time - before any test module imports the
    example bot, whose I18n instance reads the .mo at construction.
    """
    locales_root = Path(__file__).resolve().parents[2] / "examples" / "pizza_locales"
    for po_path in locales_root.glob("*/LC_MESSAGES/messages.po"):
        mo_path = po_path.with_suffix(".mo")
        if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
            continue
        with po_path.open("rb") as po_file:
            catalog = read_po(po_file)
        with mo_path.open("wb") as mo_file:
            write_mo(mo_file, catalog)


_compile_locales()
```

(`Path` is already imported in this conftest.)

- [ ] **Step 4: Write the example bot**

`examples/pizza_order_bot.py`:

```python
"""Pizza order wizard - a multi-step inline-keyboard bot with real i18n.

What this dogfoods beyond the simpler examples: CallbackData routing,
live keyboard editing (toggle buttons), mixed callback/text input,
validation branches, and aiogram's gettext i18n middleware running
through teremok's dispatch.

Note the `create_router()` factory: aiogram forbids attaching one Router
to two dispatchers, so tests build a fresh router per MockBot
(see docs/quirks.md #13).
"""

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.i18n import FSMI18nMiddleware, I18n
from aiogram.utils.i18n import gettext as _

LOCALES_DIR = Path(__file__).parent / "pizza_locales"

SIZES = {"S": 8.0, "M": 10.0, "L": 12.0}
TOPPINGS = ("Cheese", "Mushrooms", "Pepperoni", "Olives")
TOPPING_PRICE = 1.5
MIN_ADDRESS_LEN = 5

i18n = I18n(path=LOCALES_DIR, default_locale="en", domain="messages")
i18n_middleware = FSMI18nMiddleware(i18n)


class OrderStates(StatesGroup):
    choosing_language = State()
    choosing_size = State()
    picking_toppings = State()
    entering_address = State()
    confirming = State()


class LangCb(CallbackData, prefix="lang"):
    code: str


class SizeCb(CallbackData, prefix="size"):
    size: str


class ToppingCb(CallbackData, prefix="top"):
    name: str


class ActionCb(CallbackData, prefix="act"):
    action: str


def total_price(size: str, toppings: list[str]) -> float:
    return SIZES[size] + TOPPING_PRICE * len(toppings)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇬🇧 English", callback_data=LangCb(code="en").pack()
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский", callback_data=LangCb(code="ru").pack()
                ),
            ]
        ]
    )


def cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_("❌ Cancel"), callback_data=ActionCb(action="cancel").pack()
    )


def size_keyboard() -> InlineKeyboardMarkup:
    size_row = [
        InlineKeyboardButton(
            text=f"{size} ${price:.0f}", callback_data=SizeCb(size=size).pack()
        )
        for size, price in SIZES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=[size_row, [cancel_button()]])


def toppings_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for name in TOPPINGS:
        mark = "✅" if name in selected else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {_(name)}",
                    callback_data=ToppingCb(name=name).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=_("Done ➡️"), callback_data=ActionCb(action="done").pack()
            ),
            cancel_button(),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("Confirm ✅"),
                    callback_data=ActionCb(action="confirm").pack(),
                ),
                cancel_button(),
            ]
        ]
    )


def order_summary(size: str, toppings: list[str], address: str) -> str:
    toppings_text = ", ".join(_(name) for name in toppings) if toppings else _("(none)")
    return _(
        "Your order:\n"
        "Size: {size}\n"
        "Toppings: {toppings}\n"
        "Address: {address}\n"
        "Total: ${total}"
    ).format(
        size=size,
        toppings=toppings_text,
        address=address,
        total=f"{total_price(size, toppings):.2f}",
    )


async def cmd_order(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.choosing_language)
    await message.answer(_("Choose your language:"), reply_markup=language_keyboard())


async def pick_language(
    callback: CallbackQuery, callback_data: LangCb, state: FSMContext
) -> None:
    await i18n_middleware.set_locale(state, callback_data.code)
    await state.set_state(OrderStates.choosing_size)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Choose your size:"), reply_markup=size_keyboard())


async def pick_size(
    callback: CallbackQuery, callback_data: SizeCb, state: FSMContext
) -> None:
    await state.update_data(size=callback_data.size, toppings=[])
    await state.set_state(OrderStates.picking_toppings)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        _("Pick your toppings:"), reply_markup=toppings_keyboard([])
    )


async def toggle_topping(
    callback: CallbackQuery, callback_data: ToppingCb, state: FSMContext
) -> None:
    data = await state.get_data()
    selected: list[str] = data["toppings"]
    if callback_data.name in selected:
        selected.remove(callback_data.name)
    else:
        selected.append(callback_data.name)
    await state.update_data(toppings=selected)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_reply_markup(reply_markup=toppings_keyboard(selected))


async def toppings_done(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderStates.entering_address)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Send me your delivery address:"))


async def enter_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if len(address) < MIN_ADDRESS_LEN:
        await message.answer(_("Address looks too short, try again:"))
        return
    data = await state.update_data(address=address)
    await state.set_state(OrderStates.confirming)
    await message.answer(
        order_summary(data["size"], data["toppings"], address),
        reply_markup=confirm_keyboard(),
    )


async def confirm_order(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    total = total_price(data["size"], data["toppings"])
    await state.clear()
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        _("Order placed! Total: ${total}").format(total=f"{total:.2f}")
    )


async def cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Order cancelled"))


def create_router() -> Router:
    """Build a fresh wired router.

    A factory (not a module-level router) because aiogram forbids attaching
    one Router instance to a second dispatcher - each MockBot needs its own.
    """
    router = Router()
    i18n_middleware.setup(router)
    router.message.register(cmd_order, Command("order"))
    router.callback_query.register(
        pick_language, OrderStates.choosing_language, LangCb.filter()
    )
    router.callback_query.register(pick_size, OrderStates.choosing_size, SizeCb.filter())
    router.callback_query.register(
        toggle_topping, OrderStates.picking_toppings, ToppingCb.filter()
    )
    router.callback_query.register(
        toppings_done, OrderStates.picking_toppings, ActionCb.filter(F.action == "done")
    )
    router.message.register(enter_address, OrderStates.entering_address, F.text)
    router.callback_query.register(
        confirm_order, OrderStates.confirming, ActionCb.filter(F.action == "confirm")
    )
    router.callback_query.register(cancel_order, ActionCb.filter(F.action == "cancel"))
    return router
```

- [ ] **Step 5: Verify import and lint, commit**

```powershell
.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -c "import sys; sys.path.insert(0, '.'); import tests.examples.conftest; import examples.pizza_order_bot as b; r = b.create_router(); r2 = b.create_router(); print('two routers OK:', r is not r2)"
ruff check .
```

Expected: `two routers OK: True`; ruff clean. (The conftest import triggers .mo compilation; the example import then loads the catalog.) Verify `git status` shows NO `.mo` files (ignored).

```powershell
git add examples/pizza_order_bot.py examples/pizza_locales/ru/LC_MESSAGES/messages.po tests/examples/conftest.py pyproject.toml .gitignore
git commit -m "feat: pizza order wizard example - inline keyboards, FSM, gettext i18n"
```

---

### Task 2: Test suite + quirks entries

**Files:**
- Create: `tests/examples/test_pizza_order_bot.py`
- Modify: `docs/quirks.md` (rows 13-14)

**Interfaces:**
- Consumes: everything Task 1 produced; teremok top-level API.

- [ ] **Step 1: Write the tests**

`tests/examples/test_pizza_order_bot.py`:

```python
from aiogram.methods import EditMessageReplyMarkup, EditMessageText

from examples.pizza_order_bot import (
    ActionCb,
    LangCb,
    OrderStates,
    SizeCb,
    ToppingCb,
    create_router,
)
from teremok import MockBot, MockCallbackQuery, MockMessageText


def make_bot() -> MockBot:
    return MockBot(create_router())


async def start_order(bot: MockBot, lang: str = "en") -> None:
    """Drive the flow to the size screen in the given language."""
    await bot.dispatch(MockMessageText("/order"))
    await bot.dispatch(MockCallbackQuery(data=LangCb(code=lang).pack()))


async def to_toppings(bot: MockBot, size: str = "L", lang: str = "en") -> None:
    await start_order(bot, lang)
    await bot.dispatch(MockCallbackQuery(data=SizeCb(size=size).pack()))


async def test_order_shows_language_picker() -> None:
    bot = make_bot()
    result = await bot.dispatch(MockMessageText("/order"))
    assert result.handled
    sent = bot.requests.send_message[0]
    assert sent.text == "Choose your language:"
    buttons = [b for row in sent.reply_markup.inline_keyboard for b in row]
    assert [b.callback_data for b in buttons] == [
        LangCb(code="en").pack(),
        LangCb(code="ru").pack(),
    ]
    assert await bot.get_state() == OrderStates.choosing_language.state


async def test_pick_language_shows_sizes_in_english() -> None:
    bot = make_bot()
    await start_order(bot, "en")
    edit = bot.requests.edit_message_text[0]
    assert edit.text == "Choose your size:"
    size_row = edit.reply_markup.inline_keyboard[0]
    assert [b.callback_data for b in size_row] == [
        SizeCb(size="S").pack(),
        SizeCb(size="M").pack(),
        SizeCb(size="L").pack(),
    ]
    assert len(bot.requests.answer_callback_query) == 1


async def test_pick_language_shows_sizes_in_russian() -> None:
    bot = make_bot()
    await start_order(bot, "ru")
    assert bot.requests.edit_message_text[0].text == "Выбери размер:"


async def test_pick_size_shows_toppings_all_unchecked() -> None:
    bot = make_bot()
    await to_toppings(bot, "L")
    edit = bot.requests.edit_message_text[-1]
    assert edit.text == "Pick your toppings:"
    topping_rows = edit.reply_markup.inline_keyboard[:-1]
    assert all(row[0].text.startswith("⬜ ") for row in topping_rows)
    assert (await bot.get_data())["size"] == "L"


async def test_toggle_topping_on_then_off() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    first = bot.requests.edit_message_reply_markup[0]
    assert first.reply_markup.inline_keyboard[0][0].text == "✅ Cheese"
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    second = bot.requests.edit_message_reply_markup[1]
    assert second.reply_markup.inline_keyboard[0][0].text == "⬜ Cheese"
    assert (await bot.get_data())["toppings"] == []


async def test_toppings_accumulate_in_fsm_data() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Olives").pack()))
    assert (await bot.get_data())["toppings"] == ["Cheese", "Olives"]


async def test_done_asks_for_address() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="done").pack()))
    assert bot.requests.edit_message_text[-1].text == "Send me your delivery address:"
    assert await bot.get_state() == OrderStates.entering_address.state


async def test_short_address_rejected_state_kept() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.entering_address)
    await bot.set_data({"size": "S", "toppings": []})
    await bot.dispatch(MockMessageText("abc"))
    assert bot.requests.send_message[-1].text == "Address looks too short, try again:"
    assert await bot.get_state() == OrderStates.entering_address.state


async def test_valid_address_shows_summary_with_exact_total() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.entering_address)
    await bot.set_data({"size": "L", "toppings": ["Cheese", "Olives"]})
    await bot.dispatch(MockMessageText("221B Baker Street"))
    summary = bot.requests.send_message[-1]
    assert "Size: L" in summary.text
    assert "Cheese, Olives" in summary.text
    assert "221B Baker Street" in summary.text
    assert "Total: $15.00" in summary.text
    assert await bot.get_state() == OrderStates.confirming.state


async def test_confirm_places_order_and_clears_state() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.confirming)
    await bot.set_data({"size": "L", "toppings": ["Cheese", "Olives"]})
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="confirm").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order placed! Total: $15.00"
    assert await bot.get_state() is None


async def test_cancel_mid_flow_clears_state() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="cancel").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order cancelled"
    assert await bot.get_state() is None


async def test_unrelated_text_on_keyboard_step_unhandled() -> None:
    bot = make_bot()
    await start_order(bot)
    result = await bot.dispatch(MockMessageText("hello there"))
    assert not result.handled


async def test_full_flow_in_russian() -> None:
    bot = make_bot()
    await to_toppings(bot, size="M", lang="ru")
    assert bot.requests.edit_message_text[-1].text == "Выбери топпинги:"
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    markup = bot.requests.edit_message_reply_markup[-1]
    assert markup.reply_markup.inline_keyboard[0][0].text == "✅ Сыр"
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="done").pack()))
    assert bot.requests.edit_message_text[-1].text == "Пришли адрес доставки:"
    # locale survives the text-input step (lives in FSM data)
    await bot.dispatch(MockMessageText("ул. Пушкина, 1"))
    summary = bot.requests.send_message[-1]
    assert summary.text.startswith("Твой заказ:")
    assert "Итого: $11.50" in summary.text
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="confirm").pack()))
    assert bot.requests.edit_message_text[-1].text == "Заказ оформлен! Итого: $11.50"


async def test_each_callback_is_answered() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    # language pick + size pick + toggle = 3 callbacks, each answered exactly once
    assert len(bot.requests.answer_callback_query) == 3


async def test_two_bots_get_independent_routers() -> None:
    # quirk #13: a Router attaches to one dispatcher only - the factory
    # pattern must keep two MockBots fully independent
    bot_a = make_bot()
    bot_b = make_bot()
    await bot_a.dispatch(MockMessageText("/order"))
    assert bot_b.requests.all == []
    assert await bot_b.get_state() is None


def test_edit_methods_are_typed_captures() -> None:
    # sanity: the typed capture accessors used above resolve to real methods
    bot = make_bot()
    assert bot.requests.edit_message_text == []
    assert bot.requests.edit_message_reply_markup == []
    assert EditMessageText.__name__ == "EditMessageText"
    assert EditMessageReplyMarkup.__name__ == "EditMessageReplyMarkup"
```

- [ ] **Step 2: Run the suite**

```powershell
.venv\Scripts\Activate.ps1
pytest tests/examples/test_pizza_order_bot.py -v
```

Expected: 16 passed. These tests were written against the completed example (library and example both exist), so they must pass as written; a failure means either an example bug or an aiogram API mismatch — investigate, fix minimally, flag in the report.

- [ ] **Step 3: Add quirks rows**

Append to the table in `docs/quirks.md`:

```markdown
| 13 | One `Router` attaches to one dispatcher only | ✅ documented | aiogram raises "Router is already attached" if a module-level router is passed to a second `MockBot`; expose a `create_router()` factory and build a fresh router per test (see `examples/pizza_order_bot.py`); test: `test_two_bots_get_independent_routers` |
| 14 | `state.clear()` wipes the i18n locale | ✅ documented | `FSMI18nMiddleware` stores the locale in FSM data, so finishing/cancelling a flow with `state.clear()` resets the user's language to the default - re-set it or store it elsewhere if it must survive; visible in `examples/pizza_order_bot.py` |
```

- [ ] **Step 4: Full verification, commit**

```powershell
pytest
ruff check .
mypy src
coverage run --source=teremok -m pytest; coverage report --fail-under=90
python scripts/gen_coverage.py; git diff --exit-code docs/coverage.md
```

Expected: 63 passed (47 + 16), everything clean and gates green.

```powershell
git add tests/examples/test_pizza_order_bot.py docs/quirks.md
git commit -m "test: full pizza-wizard suite - callbacks, toggles, FSM, i18n end-to-end"
```

## Deviation log (updated during execution)

- **Universal cancel** (Task 1 review, plan-mandated gap): the language screen gets a `[cancel_button()]` second row and the address prompt keeps an inline cancel markup (`edit_text(..., reply_markup=InlineKeyboardMarkup(inline_keyboard=[[cancel_button()]]))`). Task 2 adjustments: `test_order_shows_language_picker` must assert the language codes on `inline_keyboard[0]` (row 0) only, and add two tests — cancel from the language screen and cancel from the address step.
