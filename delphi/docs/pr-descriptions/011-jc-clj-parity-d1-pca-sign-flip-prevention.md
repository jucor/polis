# Fix D1: implement PCA sign flip prevention matching Clojure computation

## Summary

- Add post-hoc PCA sign alignment to prevent eigenvector sign flips between
  incremental updates — Clojure achieves this via power-iteration warm-starting
  (pca.clj:86-105, conversation.clj:382); we achieve the same effect by
  comparing dot products of new vs previous components and negating when needed
- New `align_pca_signs()` function in `pca.py` handles dimension mismatches
  (new comments added), None previous components (first run), and mixed flip
  scenarios
- `conversation.py` passes previous components to `pca_project_dataframe` on
  each recompute
- D1b (projection input difference) documented as low severity, no code change
  needed

## Why this matters

Without sign alignment, when new votes arrive and PCA is recomputed, principal
components can arbitrarily flip sign. This causes participants to appear to jump
to the opposite side of the 2D visualization — a confusing user experience.
Clojure's power iteration with warm-starting naturally avoids this.

## Test plan

- [x] `test_align_pca_signs_function_exists` — function importable
- [x] `test_align_flips_negated_components` — negated components restored
- [x] `test_align_preserves_already_aligned` — same-sign components unchanged
- [x] `test_align_handles_mixed_flips` — partial flip scenario
- [x] `test_align_handles_dimension_mismatch` — wider matrix (new comments)
- [x] `test_align_returns_copy_not_mutation` — no input mutation
- [x] `test_align_with_none_prev_is_noop` — first-run passthrough
- [x] `test_projections_consistent_across_updates` — integration: ≥85%
  participants maintain direction
- [x] `test_pca_project_dataframe_accepts_prev_comps` — API check
- [x] `test_conversation_passes_prev_comps` — positive dot product across
  updates
- [x] Full test suite: **348 passed, 0 failed, 10 skipped, 53 xfailed, 1 xpassed**
