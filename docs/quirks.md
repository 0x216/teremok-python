# Known quirks and edge cases

Every entry here has either a regression test or a documented workaround.
Found a new one? Open an issue - it goes on this list with a test.

| # | Quirk | Status | Notes |
|---|---|---|---|
| 1 | `message_id` counters are **per chat**, not global | ✅ handled | `AutoResponder.next_message_id`; test: `test_message_ids_increment_per_chat_not_globally` |
| 2 | `callback_query.answer()` must work without queueing a result | ✅ handled | bool-returning methods auto-answer `True`; test: `test_bool_returning_methods_auto_answer_true` |
| 3 | `message_thread_id` (topics) passthrough | ✅ handled | builders accept it via kwargs; test: `test_kwargs_pass_through_to_message`. FSM helpers key state without thread_id (aiogram's default strategy); topic-scoped FSM strategies need a hand-built `StorageKey` |
| 4 | Media groups (albums) | ✅ handled | incoming: pass `media_group_id=` to media builders (one update per photo, like real Telegram); outgoing: `SendMediaGroup` auto-response returns one `Message` per item; test: `test_media_group_auto_response_returns_message_per_item` |
| 5 | `edited_message` is a different update type than `message` | ✅ handled | use `MockUpdate(edited_message=...)`; test: `test_edited_message_via_mock_update` |
| 6 | FSM `StorageKey` must include `bot_id` exactly as aiogram builds it | ✅ handled | `MockBot.fsm()` uses `self.id`; a mismatch silently reads/writes a different state bucket; tests in `tests/test_fsm.py` |
| 7 | All `InputFile` variants must be assertable on captured methods | ✅ handled | capture happens before serialization, so `BufferedInputFile.data/.filename`, `FSInputFile.path`, `URLInputFile.url` are all intact; test: `test_incoming_photo_download_and_typed_outgoing_capture` |
| 8 | `Message.reply_markup` only accepts inline keyboards | ✅ documented | auto-responses echo `reply_markup` only when it's an `InlineKeyboardMarkup`; reply keyboards are asserted on the captured method instead |
| 9 | String `chat_id` (e.g. `"@channel"`) in auto-responses | ✅ documented | synthesized chat gets `id=0`, `type="channel"`, `title="@channel"`; use `add_result` for realistic channel posts |
| 10 | Mocked results are validated, bot-bound COPIES | ✅ handled | all results (queued and auto) route through `check_response` with `model_validate(context={"bot": bot})` exactly like real sessions, so chaining (`sent.delete()`) works; equality with your original object should be asserted via `model_dump()` (pydantic private `_bot` differs); test: `test_queued_result_is_bound_to_bot_for_chaining` |
| 11 | Multiple registered files with suffix-overlapping paths | ✅ handled | `stream_content` extracts the exact `file_path` from the download URL and requires an exact match - no suffix collisions; test: `test_multiple_files_with_suffix_overlapping_paths` |
