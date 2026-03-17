# Fix load_votes() timestamp ordering for correct vote revision handling

## Summary

- `load_votes()` and `create_test_conversation()` in `tests/common_utils.py`
  read CSV rows in arbitrary file order, causing vote revisions to resolve
  incorrectly when `drop_duplicates(keep='last')` is applied downstream
- Fix: sort by `timestamp` column before processing, matching production
  behavior (`run_math_pipeline.py` queries `ORDER BY v.created`)
- Gracefully handles CSVs without a `timestamp` column (no-op)
- Also adds PR 15 and PR 16 (parity gate) to the discrepancy fixes plan

## Why this matters

When a participant revises their vote (e.g. agree → disagree), the CSV may
contain both rows in arbitrary order. Without sorting by timestamp:

- `load_votes()`: `drop_duplicates(keep='last')` in `update_votes()` keeps the
  last CSV row, which may be the older vote
- `create_test_conversation()`: last matrix write wins, same problem

Production is safe (Postgres `ORDER BY v.created`), but the test path was
silently wrong. This could cause false parity mismatches in PR 16 (parity gate).

## Test plan

- [x] `test_revision_keeps_latest_vote` — `load_votes()` output order with
  reversed CSV rows
- [x] `test_revision_through_conversation_update` — end-to-end through
  `Conversation.update_votes()`, verifying rating matrix value
- [x] `test_revision_in_matrix_keeps_latest` — `create_test_conversation()`
  path with monkeypatched dataset files
- [x] `test_no_timestamp_column_still_works` — graceful fallback, no crash
- [x] TDD: all 3 revision tests confirmed RED before fix, GREEN after
- [x] Full suite: 352 passed, 10 skipped, 53 xfailed, 1 xpassed — no regressions

🤖 Generated with [Claude Code](https://claude.com/claude-code)
