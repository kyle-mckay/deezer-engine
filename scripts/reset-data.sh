#!/bin/bash
# This script resets runtime data directories (db, logs, cache, exports) to a clean state without removing config or strategies.
#     Optional flag: --run to execute the engine immediately after reset.
set -e

DATA_DIRS=(data/db data/logs data/cache data/backups data/tmp data/exports)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RUN_AFTER=false
for arg in "$@"; do
    case "$arg" in
        --run) RUN_AFTER=true ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--run]"
            exit 1
            ;;
    esac
done

echo "=== Deezer Engine: Reset Runtime Data ==="
echo "Repo root: $REPO_ROOT"
echo
echo "Preserving: data/config.yml, data/strategies.yml, data/backups"
echo

# Wipe runtime subdirectories 
for dir in "${DATA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        if [[ "$dir" == "data/logs" ]]; then
            # Remove everything in data/logs except data/logs/pytest
            find "$dir" -mindepth 1 -maxdepth 1 ! -name 'pytest' -exec rm -rf {} +
        else
            rm -rf "$dir"
        fi
        if [ $? -eq 0 ]; then
            echo "Cleared $dir"
        else
            echo "ERROR: Failed to clear $dir. Please check permissions and try again."
        fi
    fi
done

echo "Runtime data cleared and directories recreated."
echo

if [ "$RUN_AFTER" = true ]; then
    echo "=== Running deezer_engine ==="
    echo
    # shellcheck disable=SC1091
    [ -f .venv/bin/activate ] && source .venv/bin/activate
    PYTHONPATH=app python -m deezer_engine
fi
