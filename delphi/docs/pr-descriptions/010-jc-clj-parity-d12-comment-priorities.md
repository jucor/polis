# Fix D12: implement comment priorities matching Clojure

## Summary

- Implement `pca_comment_extremity()` — computes L2 norm of each comment's PCA projection, matching Clojure's `pca-project-cmnts` (pca.clj:167-178)
- Implement `_compute_comment_priorities()` — full priority pipeline matching Clojure's `comment-priorities` fnk (conversation.clj:638-669): aggregate vote counts across in-conv participants, compute importance metric with Beta prior, apply new-comment boost, square for deeper bias
- Meta (promoted) comments get fixed priority = 49 (7^2), matching Clojure's `meta-priority`
- Previously, Python did not compute comment priorities, causing TypeScript server to fall back to uniform random comment selection

## Details

**Comment extremity** creates a virtual "vote vector" for each comment (all nils except -1 at position i), projects it through PCA with sparsity-aware scaling (sqrt(n_cols)), and takes the L2 norm. This measures how "extreme" a comment is in the opinion space.

**Priority formula:**
```
p = (P + 1) / (S + 2)   # pass probability (Beta prior)
a = (A + 1) / (S + 2)   # agree probability (Beta prior)
importance = (1 - p) * (E + 1) * a
boost = 1 + 8 * 2^(-S/5)   # new-comment boost
priority = (importance * boost)^2
```

**Known Clojure bug documented but not replicated:** When `meta-tids` is null (cold-start blobs generated before the poller sets meta-tids from DB), Clojure treats `(if 0 ...)` as truthy, making ALL priorities 49.0. Python does not replicate this bug.

**Clojure group-votes lag:** The Clojure `comment-priorities` fnk shadows graph-computed `group-votes` with the PREVIOUS iteration's value (`(:group-votes conv)`). For cold-start (single update), this is equivalent. For stable datasets (vw), formula matches exactly. For biodiversity, there are mismatches due to this lag — documented in tests.

## Test plan

- [x] `test_comment_priorities_exist` — Python produces non-empty priorities for all datasets
- [x] `test_comment_priorities_formula_from_blob` — recomputes from Clojure blob inputs, verifies formula match (xfail strict=False for group-votes lag)
- [x] `test_comment_priorities_ranking` — Spearman rank correlation ≥ 0.5 between Python e2e and Clojure
- [x] `test_comment_priorities_all_positive` — all values non-negative (squared formula)
- [x] Legacy `test_comment_priorities` — xfail updated to reflect priorities ARE computed
- [x] Golden snapshots re-recorded
- [x] Full test suite passes (338 passed, 0 failed)

## Test results

D12 targeted (2 datasets × 2 blob types):
- 10 passed, 4 skipped (cold-start all-49 bug), 1 xfailed (biodiversity formula lag), 1 xpassed (vw formula matches exactly)

Full suite:
- 338 passed, 0 failed, 10 skipped, 53 xfailed, 1 xpassed
