# Strict API rules (v0.2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make teremok reject what real Telegram rejects — documented Bot API rules validated in `MockedSession`, failing with genuine `TelegramBadRequest` — per the spec at `docs/superpowers/specs/2026-07-14-strict-api-rules-design.md`. Ship as v0.2.0.

**Architecture:** New pure module `src/teremok/validation.py` (rule registry, attribute-driven dispatch, internal `ApiRuleViolation`), hooked into `MockedSession.make_request` before queue/auto handling, routed through the existing `check_response` so violations surface as the same exception type and shape real Telegram produces. On by default; `validate=False` escape hatch on both `MockedSession` and `MockBot`.

**Tech Stack:** stdlib only (re, html-free hand parser). No new dependencies.

## Global Constraints

- Repo root: `C:\Users\ant\teremok`; venv `.venv\Scripts\Activate.ps1` (PowerShell; Python 3.14, aiogram 3.29.1).
- **Documented rules only.** Every enforced rule cites core.telegram.org/bots/api in `docs/validation.md` (Task 5). Where docs and observed reality diverge (e.g. docs say `>` must be escaped in HTML mode but real API accepts it), prefer ACCEPT — a false 400 is worse than a missed one — and record the decision.
- Error descriptions mimic real API shapes (`Bad Request: message text is empty`, `Bad Request: can't parse entities: ...`, `Bad Request: BUTTON_DATA_INVALID`) but tests match on stable prefixes via `pytest.raises(..., match=...)`, never on full exact strings with byte offsets.
- Lengths and entity offsets are counted in UTF-16 code units (the unit the Bot API uses for entities; documented as a project decision in validation.md and quirks).
- TDD per rule: the 400 case AND the boundary green case (e.g. exactly 4096 passes). `ruff check .` + `mypy src` clean before each commit; stage by name.
- All existing 65 tests must stay green with validation ON (they send valid payloads; if one turns out invalid, that is a finding to fix in the test/example, flagged in the report).
- Version stays 0.1.0 until Task 5 flips it to 0.2.0.

---

### Task 1: Validation core — module, session hook, lengths, entities, escape hatch

**Files:**
- Create: `src/teremok/validation.py`
- Modify: `src/teremok/session.py`, `src/teremok/bot.py`, `src/teremok/__init__.py`
- Test: `tests/test_validation_core.py`

**Interfaces:**
- Consumes: `MockedSession.make_request`, `check_response` routing (existing).
- Produces (used by Tasks 2-4):
  - `class ApiRuleViolation(Exception)` with `.description: str`
  - `validate_method(bot: Bot, method: TelegramMethod[Any]) -> None`
  - `_utf16_len(text: str) -> int`
  - `_resolve_parse_mode(bot, value) -> str | None` (resolves aiogram `Default` sentinel via `bot.default`)
  - `validate_html(text: str) -> None` and `validate_markdown(text: str, version: int) -> None` — **stubs in this task** (accept everything); Tasks 2-3 replace their bodies. `_check_parse_mode` dispatches: `"HTML"` → `validate_html`, `"MarkdownV2"` → `validate_markdown(text, 2)`, `"Markdown"` → `validate_markdown(text, 1)`.
  - `MockedSession(strict=False, validate=True)`; `MockBot(..., validate=True)` passthrough.

- [ ] **Step 1: Write failing tests**

`tests/test_validation_core.py`:

```python
import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import MessageEntity

from teremok import MockBot


def make_bot(**kwargs) -> MockBot:
    return MockBot(Router(), **kwargs)


async def test_empty_text_rejected_like_real_api() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message text is empty"):
        await bot.send_message(chat_id=1, text="")


async def test_text_over_4096_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message is too long"):
        await bot.send_message(chat_id=1, text="x" * 4097)


async def test_text_exactly_4096_passes() -> None:
    bot = make_bot()
    msg = await bot.send_message(chat_id=1, text="x" * 4096)
    assert msg.message_id >= 1


async def test_length_counted_in_utf16_units() -> None:
    bot = make_bot()
    # emoji outside BMP = 2 UTF-16 units: 2048 emoji = 4096 units -> passes
    await bot.send_message(chat_id=1, text="😀" * 2048)
    # 2049 emoji = 4098 units -> rejected
    with pytest.raises(TelegramBadRequest, match="too long"):
        await bot.send_message(chat_id=1, text="😀" * 2049)


async def test_caption_over_1024_rejected_and_boundary_passes() -> None:
    bot = make_bot()
    from aiogram.types import BufferedInputFile

    photo = BufferedInputFile(b"x", filename="p.jpg")
    await bot.send_photo(chat_id=1, photo=photo, caption="c" * 1024)
    with pytest.raises(TelegramBadRequest, match="caption is too long"):
        await bot.send_photo(chat_id=1, photo=photo, caption="c" * 1025)


async def test_edit_message_text_validated_too() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="message text is empty"):
        await bot.edit_message_text(chat_id=1, message_id=1, text="")


async def test_answer_callback_query_text_limit_200() -> None:
    bot = make_bot()
    await bot.answer_callback_query(callback_query_id="1", text="t" * 200)
    with pytest.raises(TelegramBadRequest, match="MESSAGE_TOO_LONG"):
        await bot.answer_callback_query(callback_query_id="1", text="t" * 201)


async def test_entity_out_of_range_rejected() -> None:
    bot = make_bot()
    entity = MessageEntity(type="bold", offset=3, length=10)
    with pytest.raises(TelegramBadRequest, match="entit"):
        await bot.send_message(chat_id=1, text="hello", entities=[entity])


async def test_entity_in_range_passes_with_utf16_offsets() -> None:
    bot = make_bot()
    text = "😀 bold"  # emoji = 2 units, space at 2, 'bold' at 3..7
    entity = MessageEntity(type="bold", offset=3, length=4)
    msg = await bot.send_message(chat_id=1, text=text, entities=[entity])
    assert msg.message_id >= 1


async def test_validation_off_escape_hatch() -> None:
    bot = make_bot(validate=False)
    msg = await bot.send_message(chat_id=1, text="x" * 5000)
    assert msg.message_id >= 1


async def test_offending_method_still_captured() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest):
        await bot.send_message(chat_id=1, text="")
    assert len(bot.requests.send_message) == 1
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `rtk pytest tests/test_validation_core.py -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'validate'` and missing-module errors.

- [ ] **Step 3: Implement**

`src/teremok/validation.py`:

```python
"""Documented Bot API rules, enforced the way real Telegram enforces them.

Every rule here cites the Bot API docs (see docs/validation.md). Violations
raise ApiRuleViolation; MockedSession converts them into genuine
TelegramBadRequest via the same check_response route as real error responses.
"""

from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import InlineKeyboardMarkup

MAX_TEXT = 4096  # sendMessage: "1-4096 characters after entities parsing"
MAX_CAPTION = 1024  # sendPhoto etc.: "0-1024 characters after entities parsing"
MAX_CALLBACK_ANSWER = 200  # answerCallbackQuery: "0-200 characters"


class ApiRuleViolation(Exception):
    """A documented Bot API rule was violated by an outgoing method."""

    def __init__(self, description: str) -> None:
        self.description = description
        super().__init__(description)


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _resolve_parse_mode(bot: Bot, value: Any) -> str | None:
    if isinstance(value, Default):
        resolved = getattr(bot.default, value.name, None)
        return resolved if isinstance(resolved, str) else None
    return value if isinstance(value, str) else None


def validate_html(text: str) -> None:  # replaced in the HTML task
    return


def validate_markdown(text: str, version: int) -> None:  # replaced in the Markdown task
    return


def _check_parse_mode(text: str, parse_mode: str | None) -> None:
    if parse_mode is None:
        return
    mode = parse_mode.upper()
    if mode == "HTML":
        validate_html(text)
    elif mode == "MARKDOWNV2":
        validate_markdown(text, 2)
    elif mode == "MARKDOWN":
        validate_markdown(text, 1)


def _check_entities(text: str, entities: list[Any]) -> None:
    limit = _utf16_len(text)
    for entity in entities:
        if entity.offset < 0 or entity.length < 0 or entity.offset + entity.length > limit:
            raise ApiRuleViolation(
                "Bad Request: can't parse entities: entity out of text bounds"
            )


def _check_body(bot: Bot, method: TelegramMethod[Any], text: str, entities: Any) -> None:
    if entities:
        _check_entities(text, entities)
        return  # real API ignores parse_mode when entities are supplied
    parse_mode = _resolve_parse_mode(bot, getattr(method, "parse_mode", None))
    _check_parse_mode(text, parse_mode)


def _check_inline_keyboard(markup: InlineKeyboardMarkup) -> None:
    return  # replaced in the keyboard task


def validate_method(bot: Bot, method: TelegramMethod[Any]) -> None:
    if isinstance(method, (SendMessage, EditMessageText)):
        text = method.text
        if not text:
            raise ApiRuleViolation("Bad Request: message text is empty")
        if _utf16_len(text) > MAX_TEXT:
            raise ApiRuleViolation("Bad Request: message is too long")
        _check_body(bot, method, text, getattr(method, "entities", None))

    caption = getattr(method, "caption", None)
    if isinstance(caption, str):
        if _utf16_len(caption) > MAX_CAPTION:
            raise ApiRuleViolation("Bad Request: media caption is too long")
        _check_body(bot, method, caption, getattr(method, "caption_entities", None))

    if isinstance(method, AnswerCallbackQuery) and isinstance(method.text, str):
        if _utf16_len(method.text) > MAX_CALLBACK_ANSWER:
            raise ApiRuleViolation("Bad Request: MESSAGE_TOO_LONG")

    markup = getattr(method, "reply_markup", None)
    if isinstance(markup, InlineKeyboardMarkup):
        _check_inline_keyboard(markup)
```

`src/teremok/session.py` — add the hook. `__init__` gains `validate: bool = True` stored as `self.validate`; import `json` (stdlib), `ApiRuleViolation`, `validate_method` from `.validation`. At the TOP of `make_request`, right after `self.requests.append(method)`:

```python
        if self.validate:
            try:
                validate_method(bot, method)
            except ApiRuleViolation as violation:
                self.check_response(
                    bot=bot,
                    method=method,
                    status_code=400,
                    content=json.dumps(
                        {"ok": False, "error_code": 400,
                         "description": violation.description}
                    ),
                )
                raise RuntimeError("check_response must raise for error responses")
```

`src/teremok/bot.py` — `MockBot.__init__` gains `validate: bool = True`, passed as `MockedSession(strict=strict, validate=validate)`.

`src/teremok/__init__.py` — export `ApiRuleViolation` (users may want to reference it) — add to imports/`__all__`.

- [ ] **Step 4: Run the FULL suite, verify green**

Run: `rtk pytest -v` then `rtk ruff check .` and `mypy src`
Expected: all 65 existing tests still pass with validation ON (they send valid payloads) plus 12 new ones. If any existing test/example fails validation, that is a real latent bug — fix the test/example and flag it in the report.

- [ ] **Step 5: Commit**

```powershell
rtk git add src/teremok/validation.py src/teremok/session.py src/teremok/bot.py src/teremok/__init__.py tests/test_validation_core.py
rtk git commit -m "feat: validation core - lengths, entities, escape hatch (strict API rules)"
```

---

### Task 2: HTML parse_mode validator

**Files:**
- Modify: `src/teremok/validation.py` (replace the `validate_html` stub)
- Test: `tests/test_validation_html.py`

**Interfaces:** `validate_html(text: str) -> None` raising `ApiRuleViolation`. Allowed tags/attrs per Bot API "HTML style" docs.

- [ ] **Step 1: Write failing tests**

`tests/test_validation_html.py`:

```python
import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


async def send(bot: MockBot, text: str) -> None:
    await bot.send_message(chat_id=1, text=text, parse_mode="HTML")


async def test_valid_html_passes() -> None:
    bot = make_bot()
    await send(
        bot,
        '<b>bold <i>nested</i></b> <a href="https://example.com">link</a> '
        '<code class="language-python">x=1</code> <pre>block</pre> '
        '<span class="tg-spoiler">shh</span> <tg-spoiler>shh</tg-spoiler> '
        "<blockquote>q</blockquote> <blockquote expandable>q</blockquote> "
        "5 &lt; 6 &amp; 7 &#128512;",
    )
    # reaching this line without TelegramBadRequest IS the assertion
    assert len(bot.requests.send_message) == 1


async def test_unclosed_tag_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<b>oops")


async def test_mismatched_nesting_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<b><i>x</b></i>")


async def test_unsupported_tag_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="Unsupported start tag"):
        await send(bot, "<div>nope</div>")


async def test_stray_lt_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "5 < 6")


async def test_bare_ampersand_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "you & me")


async def test_bare_gt_accepted() -> None:
    # docs say to escape '>' but the real API accepts it; we must not false-400
    bot = make_bot()
    await send(bot, "5 > 4")


async def test_a_requires_href() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<a>link</a>")


async def test_span_requires_tg_spoiler_class() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, '<span class="highlight">x</span>')


async def test_unknown_attribute_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, '<b style="color:red">x</b>')


async def test_plain_text_without_parse_mode_ignores_html() -> None:
    bot = make_bot()
    msg = await bot.send_message(chat_id=1, text="<b>not parsed")
    assert msg.message_id >= 1
```

- [ ] **Step 2: Run, verify RED** — the reject-cases fail (stub accepts everything). Expected failures: every `pytest.raises` test errors with "DID NOT RAISE".

- [ ] **Step 3: Implement** — replace the `validate_html` stub in `src/teremok/validation.py`:

```python
import re

_TAG_TOKEN = re.compile(
    r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)"
    r"((?:\s+[a-zA-Z-]+(?:=(?:\"[^\"]*\"|'[^']*'))?)*)"
    r"\s*>"
)
_ATTR = re.compile(r"([a-zA-Z-]+)(?:=(?:\"([^\"]*)\"|'([^']*)'))?")
_CHAR_REF = re.compile(r"&(?:lt|gt|amp|quot|#[0-9]{1,7}|#x[0-9a-fA-F]{1,6});")

# Bot API "HTML style": tag -> allowed attributes
_HTML_ALLOWED: dict[str, frozenset[str]] = {
    "b": frozenset(), "strong": frozenset(),
    "i": frozenset(), "em": frozenset(),
    "u": frozenset(), "ins": frozenset(),
    "s": frozenset(), "strike": frozenset(), "del": frozenset(),
    "span": frozenset({"class"}),
    "tg-spoiler": frozenset(),
    "a": frozenset({"href"}),
    "code": frozenset({"class"}),
    "pre": frozenset(),
    "blockquote": frozenset({"expandable"}),
    "tg-emoji": frozenset({"emoji-id"}),
}


def _cant_parse(detail: str) -> ApiRuleViolation:
    return ApiRuleViolation(f"Bad Request: can't parse entities: {detail}")


def validate_html(text: str) -> None:
    stack: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "<":
            token = _TAG_TOKEN.match(text, i)
            if not token:
                snippet = text[i + 1 : i + 21].split(">", 1)[0] or "<"
                raise _cant_parse(f'Unsupported start tag "{snippet}"')
            closing, name, attrs_raw = token.group(1), token.group(2).lower(), token.group(3)
            if name not in _HTML_ALLOWED:
                raise _cant_parse(f'Unsupported start tag "{name}"')
            if closing:
                if not stack or stack[-1] != name:
                    raise _cant_parse(f'Unmatched end tag "{name}"')
                stack.pop()
            else:
                attrs = {
                    m.group(1).lower(): m.group(2) if m.group(2) is not None else m.group(3)
                    for m in _ATTR.finditer(attrs_raw)
                    if m.group(1)
                }
                unknown = set(attrs) - _HTML_ALLOWED[name]
                if unknown:
                    raise _cant_parse(
                        f'Unsupported attribute "{sorted(unknown)[0]}" in tag "{name}"'
                    )
                if name == "a" and "href" not in attrs:
                    raise _cant_parse('Tag "a" must have attribute "href"')
                if name == "span" and attrs.get("class") != "tg-spoiler":
                    raise _cant_parse('Tag "span" must have class "tg-spoiler"')
                if name == "tg-emoji" and not attrs.get("emoji-id"):
                    raise _cant_parse('Tag "tg-emoji" must have attribute "emoji-id"')
                stack.append(name)
            i = token.end()
        elif ch == "&":
            ref = _CHAR_REF.match(text, i)
            if not ref:
                raise _cant_parse("Unexpected character '&' (escape it as &amp;)")
            i = ref.end()
        else:
            i += 1
    if stack:
        raise _cant_parse(
            f'Can\'t find end tag corresponding to start tag "{stack[-1]}"'
        )
```

(Place `import re` with the module's imports.)

- [ ] **Step 4: Full suite + lint/type clean** — note the pizza example and README samples use `<b>/<i>` HTML: they must pass (they are valid).

- [ ] **Step 5: Commit** — `feat: strict HTML parse_mode validation`

---

### Task 3: MarkdownV2 and legacy Markdown validators

**Files:**
- Modify: `src/teremok/validation.py` (replace `validate_markdown` stub)
- Test: `tests/test_validation_markdown.py`

**Interfaces:** `validate_markdown(text: str, version: int) -> None`.

- [ ] **Step 1: Write failing tests**

`tests/test_validation_markdown.py`:

```python
import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


async def send_v2(bot: MockBot, text: str) -> None:
    await bot.send_message(chat_id=1, text=text, parse_mode="MarkdownV2")


async def test_valid_markdown_v2_passes() -> None:
    bot = make_bot()
    await send_v2(
        bot,
        "*bold* _italic_ __underline__ ~strike~ ||spoiler|| `code` "
        "[link](https://example.com) escaped dot\\. and \\* star\n"
        ">quote line",
    )


async def test_unescaped_reserved_char_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="reserved and must be escaped"):
        await send_v2(bot, "version 2.0")  # unescaped '.'


async def test_unbalanced_bold_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "*bold")


async def test_unbalanced_spoiler_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "||spoiler")


async def test_link_without_url_end_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "[text](https://example.com")


async def test_reserved_chars_fine_inside_code() -> None:
    bot = make_bot()
    await send_v2(bot, "`a.b(c)!` and ```\nx = f(1). # ok\n```")


async def test_escaped_backslash_sequences() -> None:
    bot = make_bot()
    await send_v2(bot, "literal backslash \\\\ then escaped underscore \\_")


async def test_legacy_markdown_balanced_ok_and_reserved_not_required() -> None:
    bot = make_bot()
    await bot.send_message(
        chat_id=1, text="*bold* with a plain dot. and (parens)",
        parse_mode="Markdown",
    )


async def test_legacy_markdown_unbalanced_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await bot.send_message(chat_id=1, text="*oops", parse_mode="Markdown")
```

- [ ] **Step 2: RED** — reject-cases "DID NOT RAISE".

- [ ] **Step 3: Implement** — replace the stub:

```python
_MD2_RESERVED = frozenset("_*[]()~`>#+-=|{}.!")
_MD1_DELIMS = ("```", "`", "*", "_")


def validate_markdown(text: str, version: int) -> None:
    if version == 1:
        _validate_markdown_legacy(text)
    else:
        _validate_markdown_v2(text)


def _validate_markdown_v2(text: str) -> None:
    stack: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        in_code = bool(stack) and stack[-1] in ("`", "```")
        if ch == "`":
            seq = "```" if text.startswith("```", i) else "`"
            if in_code:
                if stack[-1] == seq:
                    stack.pop()
                    i += len(seq)
                    continue
                i += 1
                continue
            stack.append(seq)
            i += len(seq)
            continue
        if in_code:
            i += 1
            continue
        if text.startswith("||", i):
            if stack and stack[-1] == "||":
                stack.pop()
            else:
                stack.append("||")
            i += 2
            continue
        if ch == "_":
            seq = "__" if text.startswith("__", i) else "_"
            if stack and stack[-1] == seq:
                stack.pop()
            else:
                stack.append(seq)
            i += len(seq)
            continue
        if ch in "*~":
            if stack and stack[-1] == ch:
                stack.pop()
            else:
                stack.append(ch)
            i += 1
            continue
        if ch == "[":
            stack.append("[")
            i += 1
            continue
        if ch == "]" and stack and stack[-1] == "[":
            stack.pop()
            if text.startswith("(", i + 1):
                end = text.find(")", i + 2)
                if end == -1:
                    raise _cant_parse("Can't find end of a URL")
                i = end + 1
                continue
            i += 1
            continue
        if ch == ">" and (i == 0 or text[i - 1] == "\n"):
            i += 1
            continue
        if ch == "|":
            # single '|' (the '||' case was handled above)
            raise ApiRuleViolation(
                "Bad Request: can't parse entities: Character '|' is reserved "
                "and must be escaped with the preceding '\\'"
            )
        if ch in _MD2_RESERVED:
            raise ApiRuleViolation(
                f"Bad Request: can't parse entities: Character '{ch}' is "
                "reserved and must be escaped with the preceding '\\'"
            )
        i += 1
    if stack:
        raise _cant_parse(f"Can't find end of {stack[-1]} entity")


def _validate_markdown_legacy(text: str) -> None:
    stack: list[str] = []
    i, n = 0, len(text)
    while i < n:
        in_code = bool(stack) and stack[-1] in ("`", "```")
        ch = text[i]
        if ch == "`":
            seq = "```" if text.startswith("```", i) else "`"
            if stack and stack[-1] == seq:
                stack.pop()
            elif not in_code:
                stack.append(seq)
            i += len(seq)
            continue
        if not in_code and ch in "*_":
            if stack and stack[-1] == ch:
                stack.pop()
            else:
                stack.append(ch)
            i += 1
            continue
        i += 1
    if stack:
        raise _cant_parse(f"Can't find end of {stack[-1]} entity")
```

Note for the implementer: this grammar intentionally prefers ACCEPT in
genuinely ambiguous corners (per Global Constraints); if a test you consider
valid gets rejected or vice versa, check against the documented MarkdownV2
grammar first and flag disagreements in your report rather than silently
tuning the parser.

- [ ] **Step 4: Full suite + lint/type clean**

- [ ] **Step 5: Commit** — `feat: strict MarkdownV2 and legacy Markdown validation`

---

### Task 4: Inline keyboard button rules

**Files:**
- Modify: `src/teremok/validation.py` (replace `_check_inline_keyboard` stub)
- Test: `tests/test_validation_keyboard.py`

- [ ] **Step 1: Write failing tests**

`tests/test_validation_keyboard.py`:

```python
import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


def kb(*buttons: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(buttons)])


async def send_kb(bot: MockBot, markup: InlineKeyboardMarkup) -> None:
    await bot.send_message(chat_id=1, text="menu", reply_markup=markup)


async def test_valid_buttons_pass() -> None:
    bot = make_bot()
    await send_kb(
        bot,
        kb(
            InlineKeyboardButton(text="cb", callback_data="x" * 64),
            InlineKeyboardButton(text="url", url="https://example.com"),
            InlineKeyboardButton(text="inline", switch_inline_query=""),
        ),
    )


async def test_callback_data_over_64_bytes_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="x" * 65)))


async def test_callback_data_counted_in_bytes_not_chars() -> None:
    bot = make_bot()
    # 33 Cyrillic chars = 66 UTF-8 bytes -> rejected
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="я" * 33)))
    # 32 Cyrillic chars = 64 bytes -> passes
    await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="я" * 32)))


async def test_empty_callback_data_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await send_kb(bot, kb(InlineKeyboardButton(text="x", callback_data="")))


async def test_button_with_no_action_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="inline keyboard button"):
        await send_kb(bot, kb(InlineKeyboardButton(text="dead button")))


async def test_button_with_two_actions_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="inline keyboard button"):
        await send_kb(
            bot,
            kb(
                InlineKeyboardButton(
                    text="both", callback_data="x", url="https://example.com"
                )
            ),
        )


async def test_edited_keyboard_validated_too() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await bot.edit_message_reply_markup(
            chat_id=1, message_id=1,
            reply_markup=kb(InlineKeyboardButton(text="x", callback_data="x" * 65)),
        )
```

- [ ] **Step 2: RED** — reject-cases "DID NOT RAISE".

- [ ] **Step 3: Implement** — replace `_check_inline_keyboard`:

```python
# InlineKeyboardButton docs: "Exactly one of the optional fields must be used"
_BUTTON_ACTION_FIELDS = (
    "url", "callback_data", "web_app", "login_url",
    "switch_inline_query", "switch_inline_query_current_chat",
    "switch_inline_query_chosen_chat", "copy_text", "callback_game", "pay",
)


def _check_inline_keyboard(markup: InlineKeyboardMarkup) -> None:
    for row in markup.inline_keyboard:
        for button in row:
            actions = [
                field for field in _BUTTON_ACTION_FIELDS
                if getattr(button, field, None) is not None
            ]
            if len(actions) != 1:
                raise ApiRuleViolation(
                    "Bad Request: can't parse inline keyboard button: exactly "
                    "one of the optional fields must be used"
                )
            if button.callback_data is not None:
                size = len(button.callback_data.encode("utf-8"))
                if not 1 <= size <= 64:
                    raise ApiRuleViolation("Bad Request: BUTTON_DATA_INVALID")
```

Note: `pay=False`/`callback_game` defaults — verify against the installed
aiogram that unset fields are `None` (not `False`); if `pay` defaults to
`False`, treat only truthy `pay` as set and flag the adjustment.

- [ ] **Step 4: Full suite + lint/type clean** — pizza/demo keyboards must pass.

- [ ] **Step 5: Commit** — `feat: inline keyboard button rules (action fields, callback_data bytes)`

---

### Task 5: Docs, changelog, version 0.2.0

**Files:**
- Create: `docs/validation.md`, `CHANGELOG.md`
- Modify: `README.md`, `docs/quirks.md`, `pyproject.toml`, `src/teremok/__init__.py`, `tests/test_package.py`

- [ ] **Step 1: docs/validation.md** — a table of every enforced rule: rule, error description prefix, Bot API docs citation (link + section name), notes. Plus a "Deliberately not enforced" section: bare `>` in HTML (docs say escape it, real API accepts), total-buttons-per-keyboard limits (not documented), chat-existence/behavioral errors (use `add_result`), MarkdownV2 ambiguous corners (accept-first policy), per-item captions inside SendMediaGroup's InputMedia payloads (planned for a later release). State the UTF-16 counting decision explicitly.

- [ ] **Step 2: README** — new "Strict API rules (v0.2.0)" section after "Custom API results and errors": 6-8 lines — what is validated, `TelegramBadRequest` fidelity, `MockBot(router, validate=False)` escape hatch, link to docs/validation.md.

- [ ] **Step 3: quirks rows 15-16** — 15: lengths/offsets counted in UTF-16 code units (why + tests); 16: `Default` parse_mode sentinel resolved via `bot.default` before validation (so default-parse_mode bots are validated; test: set `DefaultBotProperties(parse_mode="HTML")` and send broken HTML without explicit parse_mode → add this test to tests/test_validation_core.py in THIS task if not present).

- [ ] **Step 4: CHANGELOG.md** — Keep-a-Changelog format; 0.2.0 (strict API rules, validate flag, ApiRuleViolation export) and 0.1.0 (initial) entries.

- [ ] **Step 5: version bump** — pyproject `version = "0.2.0"`, `__version__ = "0.2.0"`, `tests/test_package.py` expectation updated.

- [ ] **Step 6: Full verification + commit**

```powershell
rtk pytest
rtk ruff check .
mypy src
coverage run --source=teremok -m pytest; coverage report --fail-under=90
python scripts/gen_coverage.py; git diff --exit-code docs/coverage.md
```

Commit: `chore: docs, changelog, version 0.2.0`

(Tagging `v0.2.0` and pushing is the controller's step after the final review, not part of this task.)
