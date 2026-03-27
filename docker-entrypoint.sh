#!/bin/bash

# Copyright (C) 2026 kylemmkay
# Source: https://codeberg.org/kylemmkay/deezer-engine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


set -e

# Docker entrypoint script for deezer-engine

# Function to strip surrounding quotes from environment variables
strip_quotes() {
    local value="$1"
    # Remove surrounding double quotes
    value="${value%\"}"
    value="${value#\"}"
    # Remove surrounding single quotes
    value="${value%\'}"
    value="${value#\'}"
    echo "$value"
}

setup_cron(){
    echo "Scheduler active. Schedule: $DEEZER_SCHEDULE"
    echo "Run before cron: $DEEZER_RUN_BEFORE_CRON"
    if [ "$DEEZER_RUN_BEFORE_CRON" = "true" ]; then
        setup_run
    fi
    echo "Starting scheduler loop at $(date '+%Y-%m-%d %H:%M:%S %:z')..."
    trap 'echo "Stopping scheduler..."; kill -SIGINT "$child_pid" 2>/dev/null; exit 0' SIGINT SIGTERM
    trap 'echo "Interrupting scheduler..."; kill -INT "$child_pid" 2>/dev/null; exit 0' SIGINT

    while true; do
        # Get how long until next schedule
        WAIT_SECONDS=$(python3 - <<EOF
import datetime, sys
from croniter import croniter
try:
    base = datetime.datetime.now()
    iter = croniter('$DEEZER_SCHEDULE', base)
    next_run = iter.get_next(datetime.datetime)
    print(int((next_run - base).total_seconds()))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
        )

        if [[ "$DEEZER_LOG_LEVEL" == "DEBUG" ]]; then
            NEXT_DATE=$(date -d "@$(($(date +%s) + $WAIT_SECONDS))" '+%Y-%m-%d %H:%M:%S %:z')
            echo "---------------------------------------------------------------"
            echo "Next execution: $NEXT_DATE (In $WAIT_SECONDS seconds)"
            echo "---------------------------------------------------------------"
        fi

        # Sleep and wait
        sleep "$WAIT_SECONDS" & wait $!

        echo "Triggering scheduled run: $(date '+%Y-%m-%d %H:%M:%S %:z')"
        
        # Script
        cd /deezer_engine/app
        # Run in the background
        python3 -u -m deezer_engine run &
        child_pid=$!

        # Wait for engine to finish or for signal
        wait "$child_pid"
        
        echo "$(date '+%Y-%m-%d %H:%M:%S %:z') - Run complete; waiting for next schedule"
    done
}

setup_run(){
    # Run the script once
    echo "Running deezer-engine (single execution)..."
    cd /deezer_engine/app
    exec python -m deezer_engine run
}

setup_pytest(){
    # Allow direct pytest passthrough (for -s etc)
    echo "Running pytest (passthrough mode) inside container..."
    cd /deezer_engine
    shift
    exec pytest "$@"
    exit $?
}

# Strip quotes from environment variables if present
[ -n "$DEEZER_USER_ID" ] && DEEZER_USER_ID=$(strip_quotes "$DEEZER_USER_ID") && export DEEZER_USER_ID
[ -n "$DEEZER_ARL_TOKEN" ] && DEEZER_ARL_TOKEN=$(strip_quotes "$DEEZER_ARL_TOKEN") && export DEEZER_ARL_TOKEN
[ -n "$DEEZER_CHUNK_SIZE" ] && DEEZER_CHUNK_SIZE=$(strip_quotes "$DEEZER_CHUNK_SIZE") && export DEEZER_CHUNK_SIZE
[ -n "$DEEZER_API_BATCH_SIZE" ] && DEEZER_API_BATCH_SIZE=$(strip_quotes "$DEEZER_API_BATCH_SIZE") && export DEEZER_API_BATCH_SIZE
[ -n "$DEEZER_RATE_LIMIT" ] && DEEZER_RATE_LIMIT=$(strip_quotes "$DEEZER_RATE_LIMIT") && export DEEZER_RATE_LIMIT
[ -n "$DEEZER_LOG_LEVEL" ] && DEEZER_LOG_LEVEL=$(strip_quotes "$DEEZER_LOG_LEVEL") && export DEEZER_LOG_LEVEL
[ -n "$DEEZER_WRITE_LOGS" ] && DEEZER_WRITE_LOGS=$(strip_quotes "$DEEZER_WRITE_LOGS") && export DEEZER_WRITE_LOGS
[ -n "$DEEZER_SCHEDULE" ] && DEEZER_SCHEDULE=$(strip_quotes "$DEEZER_SCHEDULE") && export DEEZER_SCHEDULE
[ -n "$DEEZER_RUN_BEFORE_CRON" ] && DEEZER_RUN_BEFORE_CRON=$(strip_quotes "$DEEZER_RUN_BEFORE_CRON") && export DEEZER_RUN_BEFORE_CRON
[ -n "$DEEZER_PRINT_BANNER" ] && DEEZER_PRINT_BANNER=$(strip_quotes "$DEEZER_PRINT_BANNER") && export DEEZER_PRINT_BANNER
[ -n "$DEEZER_PLAYLIST_CAP" ] && DEEZER_PLAYLIST_CAP=$(strip_quotes "$DEEZER_PLAYLIST_CAP") && export DEEZER_PLAYLIST_CAP
[ -n "$DEEZER_FAVORITES_CAP" ] && DEEZER_FAVORITES_CAP=$(strip_quotes "$DEEZER_FAVORITES_CAP") && export DEEZER_FAVORITES_CAP
[ -n "$DEEZER_RETENTION" ] && DEEZER_RETENTION=$(strip_quotes "$DEEZER_RETENTION") && export DEEZER_RETENTION
[ -n "$DEEZER_TRACK_STATS_REFRESH" ] && DEEZER_TRACK_STATS_REFRESH=$(strip_quotes "$DEEZER_TRACK_STATS_REFRESH") && export DEEZER_TRACK_STATS_REFRESH
[ -n "$DEEZER_ALBUM_STATS_REFRESH" ] && DEEZER_ALBUM_STATS_REFRESH=$(strip_quotes "$DEEZER_ALBUM_STATS_REFRESH") && export DEEZER_ALBUM_STATS_REFRESH
[ -n "$DEEZER_BLOCKLIST_EXPIRY_DAYS" ] && DEEZER_BLOCKLIST_EXPIRY_DAYS=$(strip_quotes "$DEEZER_BLOCKLIST_EXPIRY_DAYS") && export DEEZER_BLOCKLIST_EXPIRY_DAYS
[ -n "$DEEZER_LOG_INTERVAL" ] && DEEZER_LOG_INTERVAL=$(strip_quotes "$DEEZER_LOG_INTERVAL") && export DEEZER_LOG_INTERVAL
[ -n "$DEEZER_FILE_RETENTION" ] && DEEZER_FILE_RETENTION=$(strip_quotes "$DEEZER_FILE_RETENTION") && export DEEZER_FILE_RETENTION
[ -n "$DEEZER_VALIDATION_MODE" ] && DEEZER_VALIDATION_MODE=$(strip_quotes "$DEEZER_VALIDATION_MODE") && export DEEZER_VALIDATION_MODE

# Print banner unless disabled
: "${DEEZER_PRINT_BANNER:=true}"
if [ "$DEEZER_PRINT_BANNER" = "true" ]; then
    PYTHONPATH=/deezer_engine/app python3 -c "from deezer_engine.__version__ import __banner__, __version__; print(__banner__); print(f'Running Deezer-Engine {__version__}\n'); print('This is free software under the GNU GPL v3.0.'); print('For more details, see https://codeberg.org/kylemmkay/deezer-engine')"
    echo "----------------------------"
fi

# Check if strategies.yml exists, if not generate from template (skip for 'pytest' entrypoint)
if [ ! -f /deezer_engine/data/strategies.yml ] && [ "$1" != "shell" ] && [ "$1" != "pytest" ]; then
    echo "No strategy file detected on startup!"
    echo "------ /deezer_engine/data -----"
    ls -Rl /deezer_engine/data
    echo "---------------------------"
    cp /deezer_engine/app/strategies.yml.template /deezer_engine/data/strategies.yml
    echo ""
    echo "If you're bind mounting the '/deezer_engine/data' folder, a default strategy file has been generated at /deezer_engine/data/strategies.yml"
    echo "Please edit the file to configure your strategies before re-running the container."
    echo ""
    echo "Container will exit in 60 seconds"
    sleep 60
    exit 0
fi

# Track if DEEZER_SCHEDULE was explicitly provided (before setting default)
SCHEDULE_PROVIDED=false
if [ -n "$DEEZER_SCHEDULE" ]; then
    SCHEDULE_PROVIDED=true
fi

# Set default schedule if not provided (only needed for cron mode)
if [ -z "$DEEZER_SCHEDULE" ]; then
    DEEZER_SCHEDULE="0 3 * * *"
fi

echo "Container started with opts '$1'"
case "$1" in
    cron)
        setup_cron
        ;;
    run)
        setup_run
        ;;
    pytest)
        setup_pytest "$@"
        ;;
    shell)
        # Start an interactive shell for debugging with docker run
        exec /bin/bash -i
        ;;
    *)
        # Default behavior: if DEEZER_SCHEDULE was provided, run cron; otherwise run once
        if [ "$SCHEDULE_PROVIDED" = true ]; then
            setup_cron
        else
            setup_run
        fi
        ;;
esac