#!/bin/bash
# Utility script to create or update a local staging branch from the current branch.
set -euo pipefail

current_branch=$(git rev-parse --abbrev-ref HEAD)

if git show-ref --quiet refs/heads/staging; then
  echo "Updating existing staging branch from $current_branch"
  git branch -f staging "$current_branch"
else
  echo "Creating staging branch from $current_branch"
  git branch staging "$current_branch"
fi

echo "Done. You can checkout the staging branch with: git checkout staging"
