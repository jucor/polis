"""
PCA (Principal Component Analysis) for Pol.is.

This module wraps sklearn PCA with Pol.is-specific handling: mean imputation
of missing votes (NaN) and sparsity-aware projection scaling.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any

logger = logging.getLogger(__name__)


def align_pca_signs(
    new_comps: np.ndarray,
    prev_comps: Optional[np.ndarray],
) -> np.ndarray:
    """
    Align the signs of new PCA components to match the direction of previous components.

    SVD-based PCA (sklearn) produces eigenvectors with arbitrary signs — the
    sign can flip between runs when the data changes slightly.  Clojure avoids
    this by using power iteration warm-started from the previous components
    (pca.clj:86-105, conversation.clj:382).  We achieve the same effect as a
    post-processing step: for each component, if ``dot(new, old) < 0``, negate
    the new component so it points in the same direction as the old one.

    Args:
        new_comps: New principal components, shape (n_comps, n_cols_new).
        prev_comps: Previous principal components, shape (n_comps, n_cols_old),
            or None on the first run (returns new_comps unchanged).

    Returns:
        Copy of new_comps with signs aligned to prev_comps.
    """
    if prev_comps is None:
        return new_comps

    aligned = new_comps.copy()
    n_shared_cols = min(new_comps.shape[1], prev_comps.shape[1])
    n_shared_comps = min(new_comps.shape[0], prev_comps.shape[0])

    for i in range(n_shared_comps):
        dot = np.dot(new_comps[i, :n_shared_cols], prev_comps[i, :n_shared_cols])
        if dot < 0:
            aligned[i] = -aligned[i]

    return aligned


def pca_project_dataframe(df: pd.DataFrame,
                         n_comps: int = 2,
                         prev_comps: Optional[np.ndarray] = None,
                         ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """
    Perform PCA on a DataFrame and project participants into PCA space.

    Missing votes (NaN) are imputed with column means before PCA.
    Uses sklearn PCA internally. Projections are scaled by the square root
    of the proportion of comments each participant has seen, to account
    for vote sparsity.

    Args:
        df: DataFrame with participants as rows and comments as columns.
            Values are votes (float); NaN indicates missing/unseen.
        n_comps: Number of principal components to compute.
        prev_comps: Previous PCA components for sign alignment, or None
            on the first run.  When provided, the signs of the new
            components are aligned to match the previous ones, preventing
            sign flips that would cause participants to jump across the
            visualization.  See :func:`align_pca_signs`.

    Returns:
        Tuple of (pca_results, proj_dict) where:
        - pca_results: dict with 'center' (mean vector) and 'comps' (component matrix)
        - proj_dict: dict mapping participant IDs to 2D projection arrays
    """
    # Extract matrix data
    matrix_data = df.to_numpy(copy=True)  # Make a copy to avoid modifying the original

    # TODO(julien): we should probably ensure upstream that the DataFrame has proper type.
    # Convert to float array if not already
    if not np.issubdtype(matrix_data.dtype, np.floating):
        try:
            matrix_data = matrix_data.astype(float)
        except (ValueError, TypeError):
            # Handle mixed types using vectorized pandas operations
            # This matches old NamedMatrix behavior: NaN stays NaN, non-convertible values become 0.0
            df_temp = pd.DataFrame(matrix_data)
            original_nulls = df_temp.isna()  # Track original NaN/None values
            df_numeric = df_temp.apply(pd.to_numeric, errors='coerce')  # Convert all to numeric, strings -> NaN
            newly_nan = df_numeric.isna() & ~original_nulls  # Find values that became NaN (were strings)
            df_numeric[newly_nan] = 0.0  # Non-convertible strings become 0.0
            matrix_data = df_numeric.to_numpy(dtype='float64')
    
    # Replace NaNs with column means for PCA calculation 
    # Why column mean instead of 0? Using 0 biases covariance estimates for sparse data.
    # Column mean is imperfect (pulls participants toward center, assumes Gaussian data
    # while votes are ternary) but is better than 0. Future work needed
    # to have a more proper way to handle missing data in PCA.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # suppress "Mean of empty slice"
        col_means = np.nanmean(matrix_data, axis=0)
    # Handle columns that are entirely NaN (e.g., statements with zero votes):
    # nanmean returns NaN for these, which would leave NaNs in the matrix.
    col_means = np.where(np.isnan(col_means), 0.0, col_means)
    nan_indices = np.where(np.isnan(matrix_data))
    matrix_data_no_nan = matrix_data.copy()
    matrix_data_no_nan[nan_indices] = col_means[nan_indices[1]]
    
    # Verify there are enough rows and columns for PCA
    n_rows, n_cols = matrix_data_no_nan.shape
    if n_rows < 2 or n_cols < 2:
        # Create minimal PCA results with consistent shape
        pca_results = {
            'center': np.zeros(n_cols),
            'comps': np.zeros((min(n_comps, n_cols), n_cols))
        }
        # Create minimal projections (all zeros)
        proj_dict = {pid: np.zeros(2) for pid in df.index}
        return pca_results, proj_dict
    
    # TODO(julien): try removing random_state to see if results are deterministic without it
    # (sklearn's full SVD solver is deterministic; randomized solver needs a seed).
    
    # Perform PCA with error handling
    # TODO(julien): use function that compute projections and PCAs in one pass.
    try:
        from sklearn.decomposition import PCA

        pca = PCA(n_components=n_comps, random_state=42)
        projections = pca.fit_transform(matrix_data_no_nan)
        projections = np.ascontiguousarray(projections)

        comps = pca.components_

        # Align signs with previous components to prevent sign flips.
        # Clojure achieves this implicitly via power-iteration warm-starting
        # (pca.clj:86-105); we do it as explicit post-processing.
        if prev_comps is not None:
            aligned_comps = align_pca_signs(comps, prev_comps)
            # If any component was flipped, the corresponding projection
            # column must also be negated to stay consistent.
            for i in range(min(comps.shape[0], aligned_comps.shape[0])):
                if not np.array_equal(comps[i], aligned_comps[i]):
                    projections[:, i] = -projections[:, i]
            comps = aligned_comps

        pca_results = {
            'center': pca.mean_,
            'comps': comps
        }

    except Exception as e:
        print(f"Error in PCA computation: {e}")
        # Create fallback PCA results with consistent shape
        pca_results = {
            'center': np.zeros(n_cols),
            'comps': np.zeros((min(n_comps, n_cols), n_cols))
        }
    
    # For projection, ensure proper sparsity handling
    # by dividing every projection by the square root of the proportion
    # of comments that participant has been shown (including skipped comments).
    try:
        # Divide projections by proportion of comments seen
        n_cmnts = matrix_data.shape[1]
        n_seen = np.sum(~np.isnan(matrix_data), axis=1)  # Count non-NaN votes per participant
        # Avoid division by zero for participants with no votes (matches Clojure's (max n-votes 1))
        n_seen_safe = np.maximum(n_seen, 1)
        proportions = np.sqrt(n_seen_safe / n_cmnts)
        scaled_projections = projections / proportions[:, np.newaxis]  

        # Create a dictionary of projections by participant ID
        proj_dict = {ptpt_id: proj for ptpt_id, proj in zip(df.index, scaled_projections)}
    except Exception as e:
        print(f"Error in projection computation: {e}")
        # Create fallback projections (all zeros)
        proj_dict = {pid: np.zeros(2) for pid in df.index}

    return pca_results, proj_dict


def pca_comment_extremity(pca_results: Dict[str, np.ndarray]) -> np.ndarray:
    """
    Compute comment extremity: the L2 norm of each comment's projection in PCA space.

    Matches Clojure's ``with-proj-and-extremtiy`` (conversation.clj:338-349)
    which calls ``pca-project-cmnts`` (pca.clj:167-178).

    Clojure creates a virtual "vote vector" for each comment i: all nils except
    -1 at position i. Projected through sparsity-aware projection, this gives::

        proj[i] = sqrt(n_cols) * (-1 - center[i]) * comps[:, i]

    Extremity is the Euclidean length of that projection vector.

    Args:
        pca_results: dict with 'center' (1D array, shape n_cols) and
                     'comps' (2D array, shape n_comps × n_cols).

    Returns:
        1D array of shape (n_cols,) with the extremity for each comment.
    """
    center = pca_results['center']       # (n_cols,)
    comps = pca_results['comps']         # (n_comps, n_cols)
    n_cols = center.shape[0]

    # (-1 - center[i]) for each comment
    offset = -1.0 - center               # (n_cols,)

    # Each comment's projection: offset[i] * comps[:, i], scaled by sqrt(n_cols)
    # comps[:, i] is a column — shape (n_comps,) for each i
    # proj shape: (n_cols, n_comps)
    proj = offset[:, np.newaxis] * comps.T * np.sqrt(n_cols)

    # Extremity = L2 norm of each row
    extremity = np.linalg.norm(proj, axis=1)  # (n_cols,)
    return extremity