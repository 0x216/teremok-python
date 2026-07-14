# Strict API rule validation

Since v0.2.0, `MockedSession` checks every outgoing Bot API call against
**documented** Bot API rules before it gets a response, and fails the same
way the real API fails: a genuine `TelegramBadRequest`, raised through the
same `check_response` route as a queued/auto response, carrying a realistic
`Bad Request: ...` description. This is on by default; opt out per-bot with
`MockBot(router, validate=False)`.

Implementation: `src/teremok/validation.py`. Every rule below cites the Bot
API docs section it implements - no guessed limits. A false 400 in your test
suite is worse than a missed one, so anything not documented precisely
enough to enforce with confidence is left alone (see "Deliberately not
enforced" below).

## Enforced rules

| Rule | Error prefix | Bot API docs citation | Notes |
|---|---|---|---|
| Message text required (`SendMessage`, `EditMessageText`) | `Bad Request: message text is empty` | [sendMessage](https://core.telegram.org/bots/api#sendmessage) - `text`: "Text of the message to be sent, 1-4096 characters after entities parsing" | Same field also documented on [editMessageText](https://core.telegram.org/bots/api#editmessagetext). |
| Message text ≤ 4096 chars | `Bad Request: message is too long` | [sendMessage](https://core.telegram.org/bots/api#sendmessage) (same field) | Counted in UTF-16 code units, not Python `len()` - see "UTF-16 counting" below. Boundary-tested at exactly 4096. |
| Caption ≤ 1024 chars | `Bad Request: media caption is too long` | Documented per send-media method, e.g. [sendPhoto](https://core.telegram.org/bots/api#sendphoto) - `caption`: "0-1024 characters after entities parsing" | Applies to every outgoing method with a `caption` field (`SendPhoto`, `SendVideo`, `SendDocument`, `SendAudio`, `SendAnimation`, `SendVoice`, `EditMessageCaption`, ...) via attribute-driven dispatch, not a per-method list. |
| `parse_mode="HTML"` well-formedness | `Bad Request: can't parse entities: ...` (unsupported start tag, unmatched/unclosed tag, unsupported attribute, missing required attribute, bare `&`) | [Formatting options - HTML style](https://core.telegram.org/bots/api#formatting-options) | Enforces exactly the documented tag/attribute allow-list (`b`/`strong`, `i`/`em`, `u`/`ins`, `s`/`strike`/`del`, `span class="tg-spoiler"`, `tg-spoiler`, `a href`, `code [class="language-*"]`, `pre`, `blockquote [expandable]`, `tg-emoji emoji-id`). Bare `<` and unescaped `&` are rejected; bare `>` is deliberately accepted (see below). |
| `parse_mode="MarkdownV2"` well-formedness + escaping | `Bad Request: can't parse entities: ...` (reserved character not escaped, unbalanced entity, unterminated URL) | [Formatting options - MarkdownV2 style](https://core.telegram.org/bots/api#formatting-options) | Reserved characters `` _*[]()~`>#+-=|{}.! `` must be escaped with `\` outside entities; a balanced-delimiter stack tracks `*`, `_`/`__`, `~`, `\|\|`, `` ` ``/```` ``` ````, and `[...](...)` links. |
| `parse_mode="Markdown"` (legacy) well-formedness | `Bad Request: can't parse entities: Can't find end of ... entity` | [Formatting options - Markdown style (legacy)](https://core.telegram.org/bots/api#formatting-options) | Only delimiter balance for `*`, `_`, `` ` ``/```` ``` ```` is enforced; legacy Markdown does not mandate escaping arbitrary punctuation the way MarkdownV2 does (see "Deliberately not enforced" below). |
| `entities` / `caption_entities` bounds | `Bad Request: can't parse entities: entity out of text bounds` | [Formatting options](https://core.telegram.org/bots/api#formatting-options) (`MessageEntity` offset/length) | `offset`/`length` must be ≥ 0 and `offset + length` within the UTF-16 length of the text/caption. When `entities` is supplied, `parse_mode` is ignored, matching real API behavior. |
| `AnswerCallbackQuery.text` ≤ 200 chars | `Bad Request: MESSAGE_TOO_LONG` | [answerCallbackQuery](https://core.telegram.org/bots/api#answercallbackquery) - `text`: "0-200 characters" | |
| Exactly one `InlineKeyboardButton` action field | `Bad Request: can't parse inline keyboard button: exactly one of the optional fields must be used` | [InlineKeyboardButton](https://core.telegram.org/bots/api#inlinekeyboardbutton) - "Exactly one of the fields other than *text*, *icon_custom_emoji_id*, and *style* must be used to specify the type of the button" | Checked on every `InlineKeyboardMarkup` reachable via `reply_markup`, on both send and edit methods. |
| `InlineKeyboardButton.callback_data` 1-64 bytes | `Bad Request: BUTTON_DATA_INVALID` | [InlineKeyboardButton](https://core.telegram.org/bots/api#inlinekeyboardbutton) - `callback_data`: "1-64 bytes" | Counted in UTF-8 **bytes**, not characters - Cyrillic/CJK text hits the limit at half the character count an ASCII-based count would suggest. |

## UTF-16 counting

Telegram's Bot API measures every string length (`text`, `caption`) and
every `MessageEntity.offset`/`length` in **UTF-16 code units** - not Unicode
code points, not UTF-8 bytes (documented on the
[Formatting options](https://core.telegram.org/bots/api#formatting-options)
page, which describes entity offsets/lengths explicitly in those terms).
teremok's `_utf16_len` helper (`len(text.encode("utf-16-le")) // 2`) matches
that unit exactly.

Python's built-in `len()` would get this wrong: characters outside the Basic
Multilingual Plane - most emoji, e.g. 😀 - are a single Python `str` element
but two UTF-16 code units. Using `len()` for the 4096-char limit would let
through text the real API rejects, and would check entity offsets against
the wrong scale entirely. Every length/offset/bounds check in
`validation.py` goes through `_utf16_len`, never `len()`. The one exception
is `callback_data`, whose documented limit is byte-based (UTF-8), matching
the docs' own "1-64 bytes" wording.

## Known divergence: length counted on the raw string

The Bot API counts `text`/`caption` limits "after entities parsing" -
markup characters (`*`, `_`, `<b>`, backslash escapes, ...) are stripped
before counting. teremok currently counts the **raw** string including
markup, so a heavily-marked-up text whose parsed form fits the limit may be
false-rejected near the boundary. Precise parsed-length counting is planned.

## Validation precedence vs queued results

Validation runs **before** queued results are consulted. A call that fails
validation raises immediately and does **not** consume a queued result: the
queued result stays in place and will answer the next call of that method
type.

## Deliberately not enforced

- **Bare `>` in HTML.** The docs say to escape `>` as `&gt;`; the real Bot
  API accepts a literal `>` anyway. teremok follows the real API's observed
  behavior over the docs' wording, to avoid false-rejecting valid text
  (`tests/test_validation_html.py::test_bare_gt_accepted`).
- **Keyboard total-size limits** - e.g. "≤100 buttons per keyboard" or
  "≤8 buttons per row" circulate as community knowledge but are not stated
  in the Bot API reference. teremok does not guess at undocumented numbers;
  a wrong guess would false-reject valid keyboards.
- **Behavioral/chat-existence errors** - "chat not found", "bot was blocked
  by the user", "message to edit not found", rate limiting, and similar.
  These depend on server-side state that isn't recoverable from the request
  shape alone. Queue them explicitly instead:
  `bot.add_result(SendMessage, ok=False, error_code=400, description="Bad Request: chat not found")`.
- **MarkdownV2 ambiguous corners** - accept-first policy: where the
  documented grammar is genuinely ambiguous, teremok accepts rather than
  risk a false 400. Example: `Hi![x](url)` is accepted even though it isn't
  a real custom-emoji entity (`![emoji](tg://emoji?id=...)`) - the parser
  treats any `!` immediately followed by `[...](...)` as the custom-emoji
  construct rather than attempting to validate the URL scheme.
- **`SendMediaGroup` per-item captions.** Each `InputMediaPhoto`/
  `InputMediaVideo`/etc. inside the `media` array can carry its own
  `caption`/`parse_mode`; those nested fields are not yet validated (only
  the outer method's own `caption`/`text`, when present, is checked).
  Planned for a later release.
- **Legacy Markdown's finer escaping semantics.** Legacy Markdown is the
  least specified of the three parse modes: the docs say `_`, `*`, `` ` ``,
  `[` must be escaped with `\` to use them literally, but say nothing about
  precedence inside nested entities. teremok balances delimiters and treats
  `\` as an escape outside code spans (and as a literal character inside
  them - an unconditional skip would eat a closing `` ` `` and false-reject,
  see the comment in `_validate_markdown_legacy`), but does not attempt to
  enforce escaping beyond delimiter balance.
