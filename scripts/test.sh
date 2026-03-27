#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo "=== Deezer Engine: Tests ==="
echo

PYTHONPATH=app pytest \
    --tb=short \
    -v \
    app/tests \
    "$@"
