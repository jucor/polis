# Fix D3: match Clojure k-smoother buffer for group cluster count stability

## Summary

- Implements the k-smoother buffer from Clojure (`conversation.clj:449-468`), which prevents the number of group clusters (k) from flickering between updates
- Clojure requires the silhouette-best k to be the same for 4 consecutive updates before `smoothed_k` switches; on cold start, the first k is accepted immediately
- Adds `group_k_smoother` state dict (`last_k`, `last_k_count`, `smoothed_k`) to `Conversation`, preserved across `update_votes()` calls via the existing `deepcopy` pattern
- Cold-start behavior is unchanged: single-shot computations accept the silhouette-best k immediately since the buffer threshold (4) is not yet reached

## Changes

- `polismath/conversation/conversation.py`:
  - Added `group_k_smoother` state to `__init__`
  - Added `GROUP_K_BUFFER = 4` constant in `_compute_clusters()`
  - After silhouette selection, applies smoother logic before choosing the final clustering
- `tests/test_discrepancy_fixes.py`:
  - New `TestD3KSmootherBuffer` class with 7 synthetic tests

## Test plan

- [x] 7 D3 tests pass (smoother state, cold start, flickering, buffer switch, count reset, state persistence, cold-start equivalence)
- [x] Full test suite without `--include-local`: 322 passed, 3 skipped, 56 xfailed, 0 failed
- [x] Full test suite with `--include-local`: no new failures (3 pre-existing: pakistan-incremental D2, 2 FLI regression)
- [ ] Verify golden snapshots unchanged (cold-start single-shot, smoother has no effect)

## Notes

- No Clojure blob comparison is possible for this temporal feature — cold-start blobs are single-shot
- Full replay infrastructure (feeding votes in batches to both Python and Clojure) is needed for end-to-end comparison; deferred to a future PR
