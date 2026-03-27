#!/bin/bash
# This script sets up a local development environment for Deezer Engine:
# 1. Check Python 3.11+ and create .venv if needed.
# 2. Install dependencies from requirements.txt.
# 3. Create runtime data directories.
# 4. Seed config templates and print next steps.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIRS=(data/db data/logs data/cache data/backups data/tmp data/exports)
cd "$REPO_ROOT"

echo "=== Deezer Engine: Dev Setup ==="
echo "Repo root: $REPO_ROOT"
echo

# --- 1: Python environment ---

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed or not on PATH."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "WARNING: Python $PY_VERSION detected. Python 3.11+ (matches container baseline)."
else
    echo "Python $PY_VERSION detected. OK."
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment at $REPO_ROOT/.venv ..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists. Skipping creation."
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies from requirements.txt ..."
if pip install --quiet --no-cache-dir -r requirements.txt; then
    echo "Dependencies installed successfully."
else
    echo "ERROR: Failed to install dependencies. Please check the output above for details."
fi
echo

# --- 2: Data directory scaffold ---

echo "Creating data directories ..."
# We only really need the data for config/strategies, but creating the whole structure for convenience.
mkdir -p "${DATA_DIRS[@]}"
echo "Data directories ready."
echo

# --- 3: Template seeding ---

if [ ! -f "data/config.yml" ]; then
    cp app/config.yml.template data/config.yml
    echo "Created data/config.yml from template."
    echo
    echo "  ACTION REQUIRED: Open data/config.yml and fill in:"
    echo "    arl_token: your Deezer ARL cookie"
    echo "    user_id:   your numeric Deezer profile ID"
else
    echo "data/config.yml already exists. Skipping (credentials preserved)."
fi

if [ ! -f "data/strategies.yml" ]; then
    cp app/strategies.yml.template data/strategies.yml
    echo "Created data/strategies.yml from template."
else
    echo "data/strategies.yml already exists. Skipping."
fi

echo

# --- 4: Developer hints ---

# Ensure scripts are executable (suppress error, capture status)
chmod +x scripts/*.sh 2>/dev/null
HINT_PREFIX=""
if [ $? -eq 0 ]; then
    echo "Ensured scripts are executable."
    HINT_PREFIX="./"
else
    echo "WARNING: Could not set execute permissions (chmod +x scripts/*.sh) on scripts."
    HINT_PREFIX="bash "
fi

echo "=== Setup complete. Next steps ==="
echo
echo "  Run the engine:"
echo "    PYTHONPATH=app python -m deezer_engine"
echo
echo "  Run tests:"
echo "    ${HINT_PREFIX}scripts/test.sh"
echo
echo "  Reset runtime data (db, logs, exports) between runs:"
echo "    ${HINT_PREFIX}scripts/reset-data.sh"
echo "    ${HINT_PREFIX}scripts/reset-data.sh --run   # reset then run immediately"
echo
