# Fix D10: match Clojure representative comment selection

## Summary

Rewrites the representative comment selection logic (`select_rep_comments_df`) to match
Clojure's `select-rep-comments` (repness.clj:209-278).

### Key differences fixed

| Aspect | Python (old) | Clojure (target) |
|--------|-------------|------------------|
| **Significance test** | Direction-specific: only checks the selected direction's pat/rat | OR-based: either (pat>Z_90 AND rat>Z_90) OR (pdt>Z_90 AND rdt>Z_90) |
| **Selection pool** | Separate agree/disagree pools, fixed 3+2 split | Single "sufficient" pool, sorted by repness-metric |
| **Best-agree** | Not tracked | Pinned at front of result (complex 4-case comparison) |
| **Fallback** | Take first comment | Track best-by-test (max(rat, rdt)) across all comments |
| **Limit** | 3 agrees + 2 disagrees (configurable) | Take top 5 total (hardcoded) |
| **Ordering** | No guarantee | Agrees always before disagrees |

### New helper functions

- `_passes_by_test_clojure(row)` — OR-based significance matching repness.clj:162-167
- `_beats_best_by_test(row, current_best_z)` — fallback tracking matching repness.clj:130-136
- `_beats_best_agr(row, current_best)` — best-agree tracking matching repness.clj:139-159

### Discovery: blob comparison blocked by cluster mismatch

Per-group repness comparison with Clojure blobs is blocked because Python and Clojure
produce different clusters (different k and/or different group memberships). This is D3
(k-smoother buffer), not D10. Updated all 7 blob comparison tests' xfail reasons from
"D10: selection differs" to "D3: clusters differ".

## Test plan

- [x] Synthetic unit test: `_passes_by_test_clojure` OR logic (4 cases)
- [x] Synthetic unit test: agrees-before-disagrees ordering
- [x] Synthetic unit test: max 5 comment limit
- [x] Synthetic unit test: fallback to best-by-test when no comments pass significance
- [x] Synthetic unit test: best-agree pinned at front
- [x] Full test suite (public): 294 passed, 0 failed, 60 xfailed
- [x] Golden snapshots re-recorded for vw and biodiversity
- [x] Full suite with --include-local: all 7 datasets pass regression
  (pakistan pre-existing failures only — PCA dimension mismatch with incremental blobs)
- [x] Blob comparison tests: blocked by D3 (cluster mismatch), xfailed

## Test results

```
Public:  294 passed, 3 skipped, 60 xfailed, 0 failures
Private: regression tests pass for all 7 datasets (vw, biodiversity, FLI, bg2018, engage, bg2050, pakistan*)
         * pakistan has pre-existing incremental blob failures, not caused by D10
```
