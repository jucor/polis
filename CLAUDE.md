# Private Test Data Repository

This is a separate git repo containing private conversation datasets for Delphi regression testing. It is **not** committed to the main polis repo.

## Contents

Each directory contains exported votes, comments, and Clojure math blobs for one conversation:
- `r*-<name>/votes.json` — raw votes
- `r*-<name>/comments.json` — raw comments
- `r*-<name>/math_main.json` — Clojure cold-start math blob
- `r*-<name>/golden_snapshot.json` — Python golden snapshot for regression tests

## Linking to a Polis Worktree

Each polis worktree gets its own clone of this repo at `delphi/real_data/.local/`:

```bash
# From any existing clone:
./link-to-polis-worktree.sh /path/to/polis-worktree

# Or from within a polis worktree:
/path/to/any/existing/.local/link-to-polis-worktree.sh
```

The script:
1. Clones this repo into `delphi/real_data/.local/`
2. Checks out (or creates) a branch matching the polis branch
3. Ensures `delphi/real_data/.local` is in `.git/info/exclude`
4. Installs a `post-checkout` hook that auto-syncs branches

## Branch Policy

- Branch names mirror the polis repo branches
- On polis branch checkout, the hook switches the private data branch to match
- If no matching branch exists, one is created from `main`
- Golden snapshots are re-recorded per branch when code changes affect output

## Re-recording Golden Snapshots

When parity fixes change the output (e.g., different clustering due to threshold changes):

```bash
cd delphi
# Re-record all datasets in parallel:
uv run --extra dev python scripts/regression_recorder.py --all --include-local --force

# Then commit in the private data repo:
cd real_data/.local
git add -A && git commit -m "Re-record golden snapshots for <reason>"
git push origin <branch>
```

## IMPORTANT

- NEVER list private dataset names in any file committed to the polis repo
- Use generic references like "private datasets" or "5 private datasets in real_data/.local/"
- This repo's origin is at `~/polis/github/real_data_private` (bare, local only)
