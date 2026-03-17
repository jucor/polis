# Handoff: Cold-Start K Divergence Investigation

## Problem

After all cold-start-relevant formula fixes (D2-D15), Python and Clojure still
select different k values on cold-start blobs. On vw: Python=4, Clojure=2.

Both implementations use silhouette-based k-selection (`max-key silhouette` in
Clojure conversation.clj:458, `argmax silhouette` in Python). The divergence
must come from upstream numerical differences feeding into the silhouette scores.

## What we know

### Pipeline chain to k-selection

```
Votes → in-conv filtering [D2] → moderation [D15] → rating_mat
  → PCA [sklearn SVD vs Clojure power iteration] → projections
    → base clusters [k-means, D2b sort order] → group k-means → silhouette → k
```

### Fixes already applied (cold-start relevant)

| Fix | What it does | Status |
|-----|-------------|--------|
| D2 | In-conv threshold: `min(7, n_cmts)` | DONE |
| D2b | Base-cluster sort by k-means ID | DONE |
| D2c | Vote counts from `raw_rating_mat` | DONE |
| D15 | Zero out moderated columns (not remove) | In stack |

### D1 is NOT relevant for cold start

D1 (PCA sign flip prevention) aligns new components to previous components.
On cold start, `prev_comps` is None → alignment is a no-op. D1 only matters
for incremental updates.

### Observed divergence (vw dataset)

Python silhouette scores:
- k=2: 0.4567
- k=3: 0.4810
- k=4: 0.5083 ← winner
- k=5: 0.3892

Clojure selected k=2. We don't have Clojure's per-k silhouette scores, but
the blob tells us the result: 2 groups, 17+50 members.

### Possible causes (ranked by likelihood)

1. **PCA component differences**: sklearn `TruncatedSVD` uses randomized SVD
   (Halko et al. 2011). Clojure uses power iteration warm-started from previous
   components (pca.clj:86-105). On cold start, Clojure starts from a random
   vector. Different algorithms → different components → different projections →
   different silhouette landscape.

2. **K-means initialization**: Clojure uses `first-k-distinct` initialization
   from base-cluster centers. Python uses sklearn's `k-means++`. Different
   starting centroids → different cluster assignments → different silhouette.

3. **Distance metric in silhouette**: Verify both use the same distance
   (Euclidean on PCA-projected data). Check if Clojure computes silhouette on
   base-cluster centroids vs individual participant projections.

4. **Silhouette implementation**: Clojure's `silhouette` (clusters.clj:339)
   may compute things slightly differently from sklearn's `silhouette_score`.

## Investigation plan

### Step 1: Compare PCA components directly

```python
# Load Clojure blob PCA
clj_pca = blob['pca']  # Check structure: components, projections?

# Run Python PCA on same rating_mat
# Compare components: cosine similarity per component
```

### Step 2: Inject Clojure PCA into Python clustering

Feed Clojure's PCA projections to Python's clustering code. If k now matches
Clojure, the divergence is in PCA. If k still differs, it's in clustering
or silhouette.

### Step 3: Compare silhouette implementations

Run both Clojure and Python silhouette on the same cluster assignments.
Clojure's implementation is at `clusters.clj:339-374`. Check:
- Distance metric (Euclidean? On what data?)
- Handling of single-member clusters
- Averaging method

### Step 4: Compare k-means initialization

Check if Clojure's `first-k-distinct` from base clusters gives different
initial centroids than Python's approach.

## Files to read

- `math/src/polismath/math/clusters.clj:339-374` — Clojure silhouette
- `math/src/polismath/math/conversation.clj:440-460` — Clojure k-selection
- `math/src/polismath/math/pca.clj:86-105` — Clojure power iteration PCA
- `delphi/polismath/conversation/conversation.py` — Python clustering
- `delphi/polismath/pca_kmeans_rep/pca.py` — Python PCA

## Blob fields to use

- `pca` — Clojure's PCA output (check what's in there)
- `group-clusters` — Clojure's final group assignments
- `base-clusters` — Clojure's base-cluster assignments
- `votes-base` — may contain the projected base-cluster centers

## Expected outcomes

Either:
- **(a) Fixable**: Identify a specific implementation difference (initialization,
  distance metric, etc.) that, when fixed, makes k match on all datasets.
- **(b) Inherent divergence**: sklearn SVD and Clojure power iteration produce
  sufficiently different components that the silhouette landscape differs.
  Document the expected k divergence per dataset and tolerate it in tests.
  In this case, blob-injection tests (testing stages independently) become
  even more critical, since end-to-end comparison is not feasible.
