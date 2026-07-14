# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
