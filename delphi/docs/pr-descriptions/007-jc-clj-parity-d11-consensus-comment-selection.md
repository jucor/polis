# Fix D11: match Clojure consensus comment selection logic

## Summary

Rewrites `select_consensus_comments_df` to match Clojure's `consensus-stats` + `select-consensus-comments` (repness.clj:281-320).

**Old behavior**: Per-group aggregation — groups stats by comment across groups, checks ALL groups have pa > 0.6, takes top 2 by average pa, returns flat list.

**New behavior**: Overall vote matrix — computes per-comment stats across ALL participants (not per-group), filters by pa > 0.5 AND pat > Z_90 (one-tailed significance), ranks by am = pa × pat (or dm = pd × pdt for disagree), takes top 5 agree + top 5 disagree, returns `{agree: [...], disagree: [...]}`.

Key differences:
- **Input**: Overall vote matrix instead of per-group stats DataFrame
- **Filter**: `pa > 0.5 AND z-sig-90?(pat)` instead of `ALL groups pa > 0.6`
- **Ranking**: `am = pa * pat` product metric instead of average pa across groups
- **Limit**: 5 per side (agree + disagree) instead of 2 total
- **Output**: Dict with separate agree/disagree lists instead of flat list
- **Format**: Clojure-compatible `{tid, n-success, n-trials, p-success, p-test}` instead of `{comment_id, avg_agree, repful, stats}`

Consensus is independent of clustering (D3) — it uses the overall vote matrix, so cold-start blob comparisons match exactly.

## Files changed

- `polismath/pca_kmeans_rep/repness.py` — rewritten `select_consensus_comments_df`, updated `conv_repness()` caller
- `polismath/conversation/conversation.py` — updated empty consensus format
- `tests/test_discrepancy_fixes.py` — 4 real-data tests + 5 synthetic tests (replacing 1 xfail)
- `tests/test_repness_smoke.py` — updated consensus structure assertions
- `tests/test_pipeline_integrity.py` — updated consensus iteration for new dict format
- `real_data/*/golden_snapshot.json` — re-recorded after consensus format change

## Test plan

- [x] D11 targeted tests: 21 passed (4 real-data × 4 blob variants + 5 synthetic)
- [x] Consensus matches Clojure blob exactly on cold-start blobs (vw, biodiversity)
- [x] Incremental blob comparison: overlap check (in-conv set differs progressively)
- [x] Full test suite (public): 315 passed, 0 failed, 3 skipped, 56 xfailed
- [ ] Full test suite with --include-local (private datasets)

## Test results

```
315 passed, 0 failed, 3 skipped, 56 xfailed (public datasets)
```
