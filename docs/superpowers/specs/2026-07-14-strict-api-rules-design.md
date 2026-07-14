# Strict API rules (v0.2.0) — Design Spec

**Date:** 2026-07-14
**Status:** Approved by owner (process delegated; release authorized)

## Why

teremok's core promise is "test green ⇒ works in production". Today five
classes of requests pass teremok silently but get a 400 from real Telegram:
invalid parse_mode markup, over-limit text/caption, oversized callback_data,
out-of-range entities, malformed inline buttons. Closing this gap is pure,
verifiable fidelity work — and no competing mock does it.

## What

A validation layer in `MockedSession` that checks every outgoing method
against **documented** Bot API rules *before* answering, and fails exactly
like the real API fails: `TelegramBadRequest` raised through the existing
`check_response` route with a realistic `Bad Request: ...` description.

- **On by default.** `MockedSession(validate=False)` / `MockBot(..., validate=False)`
  as the escape hatch. This is the headline of v0.2.0 and the reason for the
  minor version bump: previously-green tests that send invalid payloads are
  *supposed* to start failing.
- **Documented rules only.** Every rule cites the Bot API docs section it
  implements. No guessed limits: a false 400 in tests is worse than a missed
  one. Known-but-undocumented limits (e.g. "100 buttons per keyboard") are
  listed in `docs/validation.md` as *not enforced* with rationale.
- Runs before queue/auto handling: real Telegram validates the request even
  when the logical reply would be an error.

## Rules in scope (each with docs citation in docs/validation.md)

1. **Message text**: 1–4096 chars; empty text → `Bad Request: message text is
   empty`; over-limit → `Bad Request: message is too long`. Applies to
   SendMessage, EditMessageText. Length counted in UTF-16 code units (the
   unit Telegram uses for entity offsets; counting choice documented).
2. **Caption**: ≤1024 chars (send-media family + EditMessageCaption),
   `Bad Request: media caption is too long`.
3. **parse_mode="HTML"**: strict well-formedness against the documented tag
   set (b/strong, i/em, u/ins, s/strike/del, span class="tg-spoiler",
   tg-spoiler, a href, code [class="language-*"], pre, blockquote
   [expandable], tg-emoji emoji-id). Stack-based parser; unknown tag →
   `Bad Request: can't parse entities: Unsupported start tag "..."`;
   unclosed/mismatched → `... Can't find end tag corresponding to start tag ...`.
4. **parse_mode="MarkdownV2"** (and legacy "Markdown"): balanced entity
   delimiters and mandatory escaping of the documented special characters
   outside entities → `Bad Request: can't parse entities: ...`. If full
   fidelity proves chaotic at the edges, the enforced subset is documented
   precisely in docs/validation.md — never guess-reject.
5. **Entities array**: offset ≥ 0, offset+length within the UTF-16 length of
   text/caption. When `entities` present, parse_mode is ignored (as real API).
6. **InlineKeyboardButton**: exactly one action field set (docs: "Exactly one
   of the optional fields must be used"); `callback_data` 1–64 **bytes**
   (UTF-8) → `Bad Request: BUTTON_DATA_INVALID`.
7. parse_mode resolution: aiogram's `Default` sentinel resolves against the
   bot's `default.parse_mode` before validation (so
   `Bot(default=DefaultBotProperties(parse_mode="HTML"))` users get validated
   too).

## Architecture

- `src/teremok/validation.py`: pure module. `validate_method(bot, method) ->
  None`, raising internal `ApiRuleViolation(description)`. Attribute-driven
  dispatch (any method with `text`/`caption`/`reply_markup`/`entities` gets
  the relevant checks) so the whole send/edit family is covered without
  per-method boilerplate.
- `MockedSession.make_request`: when `self.validate` is true, call
  `validate_method` first; on violation, route through `check_response` with
  status 400 and the realistic description → the user's code sees a genuine
  `TelegramBadRequest`.
- `docs/validation.md`: hand-written table — rule, error text, Bot API docs
  citation, enforced/not-enforced status. Linked from README and quirks.

## Testing / docs / release bar

Same bar as v0.1.0: TDD per rule (both the 400 case and the near-limit green
case, e.g. exactly 4096 chars passes), UTF-16 emoji edge tests, escape-hatch
test, ruff+mypy strict clean, coverage ≥90%, CI matrix green incl.
aiogram 3.4.1. New quirks entries for the counting-unit choice and the
Default-parse_mode resolution. `CHANGELOG.md` introduced. Version 0.2.0,
tag → PyPI via existing trusted publishing (release pre-authorized by owner).
