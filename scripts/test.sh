#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo "=== Deezer Engine: Tests ==="
echo

PYTEST_ARGS=(
    --tb=short
    -v
    app/tests
)

if [[ -n "${TEST_MARKERS:-}" ]]; then
    PYTEST_ARGS+=( -m "$TEST_MARKERS" )
fi

# Run pytest through the CLI wrapper to ensure consistent argument handling
# (path normalization, mode routing) across local source, CI source, and container execution.
PYTHONPATH=app python -m deezer_engine pytest "${PYTEST_ARGS[@]}" "$@"
