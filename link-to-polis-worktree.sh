#!/bin/bash
# Link this private data repo to a polis worktree.
#
# Creates a git worktree of this repo inside the target polis worktree at
# delphi/real_data/.local, and installs a post-checkout hook that keeps
# the private data branch in sync with the polis branch.
#
# Usage:
#   ./link-to-polis-worktree.sh /path/to/polis-worktree
#   ./link-to-polis-worktree.sh   # auto-detects if run from within a polis worktree
#
# The bare repo is discovered from this script's origin remote.
# Branches are created on-demand: if the polis branch doesn't exist in the
# private repo, it's created from main.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PRIVATE_REPO_ORIGIN="$(cd "$SCRIPT_DIR" && git remote get-url origin 2>/dev/null || true)"

# If no origin (e.g., running from bare repo), use the repo itself
if [ -z "$PRIVATE_REPO_ORIGIN" ]; then
    PRIVATE_REPO_ORIGIN="$SCRIPT_DIR"
fi

# Resolve the target polis worktree
if [ $# -ge 1 ]; then
    POLIS_WORKTREE="$(cd "$1" && pwd)"
else
    # Try to auto-detect: walk up from cwd looking for a polis worktree
    POLIS_WORKTREE="$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || true)"
    if [ -z "$POLIS_WORKTREE" ] || [ ! -d "$POLIS_WORKTREE/delphi/real_data" ]; then
        echo "Usage: $0 /path/to/polis-worktree"
        echo "  or run from within a polis worktree"
        exit 1
    fi
fi

LOCAL_DIR="$POLIS_WORKTREE/delphi/real_data/.local"
POLIS_BRANCH="$(git -C "$POLIS_WORKTREE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"

echo "Private data repo:  $PRIVATE_REPO_ORIGIN"
echo "Polis worktree:     $POLIS_WORKTREE"
echo "Polis branch:       $POLIS_BRANCH"
echo "Target .local path: $LOCAL_DIR"
echo

# --- Step 1: Handle existing .local ---
if [ -L "$LOCAL_DIR" ]; then
    echo "Removing existing symlink at $LOCAL_DIR"
    rm "$LOCAL_DIR"
elif [ -d "$LOCAL_DIR" ]; then
    if [ -d "$LOCAL_DIR/.git" ] || [ -f "$LOCAL_DIR/.git" ]; then
        EXISTING_ORIGIN="$(git -C "$LOCAL_DIR" remote get-url origin 2>/dev/null || true)"
        if [ "$EXISTING_ORIGIN" = "$PRIVATE_REPO_ORIGIN" ]; then
            echo "Already linked to the correct repo. Syncing branch..."
            # Just sync the branch
            cd "$LOCAL_DIR"
            if git show-ref --verify --quiet "refs/heads/$POLIS_BRANCH"; then
                git checkout "$POLIS_BRANCH"
            else
                git checkout -b "$POLIS_BRANCH" main
            fi
            echo "Done."
            exit 0
        fi
        echo "ERROR: $LOCAL_DIR is a git repo but with a different origin:"
        echo "  expected: $PRIVATE_REPO_ORIGIN"
        echo "  actual:   $EXISTING_ORIGIN"
        echo "Remove it manually if you want to re-link."
        exit 1
    else
        echo "ERROR: $LOCAL_DIR exists and is not a git repo. Remove it manually."
        exit 1
    fi
fi

# --- Step 2: Create worktree ---
# We clone rather than use `git worktree add` because the bare repo's
# worktree tracking doesn't play well with paths inside other git repos.
echo "Cloning private data repo..."
git clone "$PRIVATE_REPO_ORIGIN" "$LOCAL_DIR"

# Checkout matching branch
cd "$LOCAL_DIR"
if git show-ref --verify --quiet "origin/$POLIS_BRANCH" 2>/dev/null; then
    git checkout -b "$POLIS_BRANCH" "origin/$POLIS_BRANCH" 2>/dev/null || git checkout "$POLIS_BRANCH"
elif [ "$POLIS_BRANCH" != "main" ]; then
    echo "Creating new branch '$POLIS_BRANCH' from main"
    git checkout -b "$POLIS_BRANCH" main
fi

# --- Step 3: Ensure .local is in git exclude ---
# Find the polis repo's exclude file
POLIS_GIT_DIR="$(git -C "$POLIS_WORKTREE" rev-parse --git-dir)"
# For worktrees, the shared exclude is in the common dir
POLIS_COMMON_DIR="$(git -C "$POLIS_WORKTREE" rev-parse --git-common-dir)"
EXCLUDE_FILE="$POLIS_COMMON_DIR/info/exclude"

if ! grep -q "delphi/real_data/.local" "$EXCLUDE_FILE" 2>/dev/null; then
    echo "" >> "$EXCLUDE_FILE"
    echo "# Private test data (separate repo)" >> "$EXCLUDE_FILE"
    echo "delphi/real_data/.local" >> "$EXCLUDE_FILE"
    echo "Added delphi/real_data/.local to $EXCLUDE_FILE"
else
    echo "delphi/real_data/.local already in git exclude"
fi

# --- Step 4: Install/update post-checkout hook ---
HOOK_FILE="$POLIS_COMMON_DIR/hooks/post-checkout"
HOOK_MARKER="# --- private-data-sync ---"

if [ -f "$HOOK_FILE" ] && grep -q "$HOOK_MARKER" "$HOOK_FILE"; then
    echo "post-checkout hook already has private-data-sync section"
else
    echo "Installing private-data-sync in post-checkout hook"
    if [ ! -f "$HOOK_FILE" ]; then
        echo "#!/bin/bash" > "$HOOK_FILE"
        chmod +x "$HOOK_FILE"
    fi
    cat >> "$HOOK_FILE" << 'HOOKEOF'

# --- private-data-sync ---
# Sync private test data branch with polis branch on checkout.
# Installed by link-to-polis-worktree.sh from the private data repo.
_sync_private_data() {
    local flag="$1"  # 1=branch checkout, 0=file checkout
    [ "$flag" != "1" ] && return 0

    local worktree_root
    worktree_root="$(pwd)"
    local local_dir="$worktree_root/delphi/real_data/.local"

    [ ! -d "$local_dir/.git" ] && [ ! -f "$local_dir/.git" ] && return 0

    local polis_branch
    polis_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
    [ -z "$polis_branch" ] || [ "$polis_branch" = "HEAD" ] && return 0

    (
        cd "$local_dir"
        if git show-ref --verify --quiet "refs/heads/$polis_branch" 2>/dev/null; then
            git checkout "$polis_branch" --quiet 2>/dev/null
        elif git show-ref --verify --quiet "refs/remotes/origin/$polis_branch" 2>/dev/null; then
            git checkout -b "$polis_branch" "origin/$polis_branch" --quiet 2>/dev/null
        else
            git checkout -b "$polis_branch" main --quiet 2>/dev/null
        fi
    ) || true  # Never fail the polis checkout
}
_sync_private_data "${3:-0}"
# --- end private-data-sync ---
HOOKEOF
fi

echo
echo "Done! Private data linked at $LOCAL_DIR"
echo "Branch '$POLIS_BRANCH' checked out."
echo "The post-checkout hook will auto-sync branches on future checkouts."
