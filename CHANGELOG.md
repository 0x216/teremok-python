# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-18

### Added

- **Callback-answer discipline** (opt-in via `strict_answer=True` on
  `MockBot`/`MockedSession`). Models two real Bot API behaviours the mock used
  to paper over:
  - a callback query answered **twice** now raises the same `TelegramBadRequest`
    the live API returns (`query is too old ... or query ID is invalid`);
  - a dispatched callback that the handler returned from **without** answering
    fails the step with `CallbackNotAnswered` - the eternal-spinner bug the user
    sees on the button but a green mock never did.
  - Per-step assertion `DispatchResult.assert_answered()` works with the flag
    off, so a single step can be checked without global strictness.
  - `DispatchResult` gained `callback_query_id` and `answered`;
    `MockedSession.answered_callbacks` records answered ids.
  - `CallbackNotAnswered` exported from the package root.
- **Message-id + edit + stale-message lifecycle.** Edits now keep the original
  `message_id` (like Telegram) instead of burning a new one; editing an inline
  message (`inline_message_id`) returns `True`. `MockBot.sent_messages` /
  `MockBot.last_message` expose the on-screen message history, so a test can tap
  an inline button on an **earlier, now-stale** message and reach a handler's
  "screen out of date" branch.
- **Redis-backed FSM storage for tests** via the optional `redis` extra
  (`pip install teremok[redis]`): `fake_redis_storage()` returns a real aiogram
  `RedisStorage` over an in-process fakeredis - same JSON serialization and key
  builder as production, no server. Pass it as `MockBot(router, storage=...)`.
  Surfaces state/data bugs `MemoryStorage` hides (e.g. non-JSON values).

### Changed

- `strict_answer` and `storage` are new keyword-only options on `MockBot`;
  existing calls are unaffected (both default to the previous behaviour). No
  breaking changes - `strict_answer` is opt-in precisely so existing suites that
  dispatch un-answered callbacks stay green.

## [0.2.0] - 2026-07-14

### Added

- Strict validation of outgoing Bot API calls, **on by default**: message/caption
  length limits, HTML/MarkdownV2/legacy-Markdown well-formedness, entity offset
  bounds, and inline keyboard button shape. Violations raise a genuine
  `TelegramBadRequest` through the same `check_response` route as a real
  rejection. See [docs/validation.md](docs/validation.md) for the full rule
  reference and what's deliberately not enforced.
- `validate=False` escape hatch on `MockBot`/`MockedSession` for tests that
  intentionally send malformed payloads.
- `ApiRuleViolation` exported from the package root.
- `docs/validation.md`.

## [0.1.0] - 2026-07-14

### Added

- Initial release: black-box testing for aiogram 3.x bots via a mocked
  session - typed request capture (every Bot API method), configurable
  auto-responses, `add_result`/`strict` queueing, FSM helpers, incoming file
  download support, and a generated Bot API coverage table.
