# Pizza order example — Design Spec

**Date:** 2026-07-14
**Status:** Approved by owner (process delegated, no checkpoints requested)

## What

A hard-dogfood example for teremok: `examples/pizza_order_bot.py` — a multi-step
inline-keyboard wizard with real i18n — plus a full test suite
`tests/examples/test_pizza_order_bot.py`. Small enough for `examples/`
(~200 lines), complex enough to exercise the parts of teremok no current
example touches: CallbackData routing, live keyboard editing, mixed
callback/text input, validation branches, and aiogram middleware (gettext
i18n) running through `dispatch()`.

## Flow

`/order` → **language picker** (🇬🇧/🇷🇺, `FSMI18nMiddleware.set_locale`) →
**size** (S $8 / M $10 / L $12, inline) → **toppings** (4 items à $1.50,
✅/⬜ toggles re-rendered via `edit_message_reply_markup`, Done/Cancel) →
**address** (text input, FSM; < 5 chars → localized "too short" retry, state
kept) → **summary** (size, toppings, address, exact total) with Confirm/Cancel
→ Confirm: localized "Order placed! Total: $X.XX", state cleared. ❌ Cancel on
any screen → localized "Order cancelled", state cleared.

## i18n

- Standard `aiogram.utils.i18n`: `I18n` + `FSMI18nMiddleware` (locale lives in
  FSM data — dogfoods storage integration), all strings through `gettext as _`.
- English lives in msgids; single translation catalog
  `examples/pizza_locales/ru/LC_MESSAGES/messages.po` (committed, readable).
  Binary `.mo` is compiled on the fly in `tests/examples/conftest.py` via
  Babel (`read_po`/`write_mo`, no subprocess) and git-ignored.
- Babel goes to **dev extras only** — the teremok package keeps its
  aiogram-only dependency.

## Architecture note: router factory

aiogram forbids attaching one `Router` to two dispatchers, so N tests × 
`MockBot(router)` on a module-level router explodes on the second test. The
example therefore exposes `create_router() -> Router` (plain async handler
functions + explicit `router.message.register(...)` wiring + 
`i18n_middleware.setup(router)`), and each test builds a fresh router. This is
the recommended real-world pattern for testable aiogram bots and gets
documented as quirk #13. The `state.clear()`-wipes-locale caveat of
`FSMI18nMiddleware` becomes quirk #14.

## Tests (~14)

Language picker shown; size screen localized (ru and en variants); size pick
edits message; topping toggle on→off (two dispatches, markup assertions);
toppings accumulate in FSM data; Done asks address + sets state; short address
rejected, state kept; valid address → summary with exact total ($15.00 for
L + 2 toppings, seeded mid-flow via `set_state`/`set_data`); Confirm →
localized success + state cleared; Cancel mid-flow → cancelled + cleared;
unrelated text on a keyboard step → `handled=False`; full flow in Russian
asserting Russian strings end-to-end incl. locale surviving the text-input
step.

## Constraints

- Files: `examples/pizza_order_bot.py`, `examples/pizza_locales/ru/LC_MESSAGES/messages.po`,
  `tests/examples/conftest.py` (extend), `tests/examples/test_pizza_order_bot.py`,
  `pyproject.toml` (babel dev dep), `.gitignore` (*.mo), `docs/quirks.md` (rows 13-14).
- Tests import only from `teremok` top level (+ the example module).
- ruff clean; mypy scope (`src/`) unaffected; coverage gate unaffected
  (measures `src/teremok` only); CI must stay green incl. aiogram 3.4.1 leg —
  `aiogram.utils.i18n` and `CallbackData` both exist since well before 3.4.
- No new PyPI release needed: examples ship in the repo, not the wheel.
