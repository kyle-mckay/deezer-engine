#!/bin/bash
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
    echo "Cron schedule set to: $DEEZER_SCHEDULE"
    echo "Configuring environment for cron task..."
    
    # We save all DEEZER_ variables to a file. 
    env | grep '^DEEZER_' > /app/env_config.env
    echo "TZ=${TZ:-UTC}" >> /app/env_config.env
    echo "CONTAINERIZED=true" >> /app/env_config.env

    # Ensure logging infrastructure exists
    mkdir -p /app/data/logs
    touch /app/data/logs/cron.log
    
    # Build and install the crontab
    {
        echo "SHELL=/bin/bash"
        echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        echo ""
        # The command sequence:
        # - Load the env file (source)
        # - Move to the app directory
        # - Run the engine and pipe both output and errors to the log file
        # - After the run completes, write a timestamped completion message to container stdout
        printf '%s %s\n' "$DEEZER_SCHEDULE" ". /app/env_config.env && cd /app && /usr/local/bin/python deezer-engine.py >> /app/data/logs/cron.log 2>&1; echo \"$(date -u '+%Y-%m-%d %H:%M:%S %Z') - Cron run complete; waiting for next schedule\" > /proc/1/fd/1"
    } | crontab -
    
    # Launch the services
    echo "Starting scheduler at $(date)... (Logs will stream below)"
    
    service cron start
    
    # Effectively hands over control to the log stream
    tail -f -n 0 /app/data/logs/cron.log
}

setup_run(){
    # Run the script once
    echo "Running deezer-engine (single execution)..."
    cd /app
    exec python deezer-engine.py
}

# Strip quotes from environment variables if present
[ -n "$DEEZER_USER_ID" ] && DEEZER_USER_ID=$(strip_quotes "$DEEZER_USER_ID") && export DEEZER_USER_ID
[ -n "$DEEZER_ARL_TOKEN" ] && DEEZER_ARL_TOKEN=$(strip_quotes "$DEEZER_ARL_TOKEN") && export DEEZER_ARL_TOKEN
[ -n "$DEEZER_BATCH_SIZE" ] && DEEZER_BATCH_SIZE=$(strip_quotes "$DEEZER_BATCH_SIZE") && export DEEZER_BATCH_SIZE
[ -n "$DEEZER_LOG_LEVEL" ] && DEEZER_LOG_LEVEL=$(strip_quotes "$DEEZER_LOG_LEVEL") && export DEEZER_LOG_LEVEL
[ -n "$DEEZER_WRITE_LOGS" ] && DEEZER_WRITE_LOGS=$(strip_quotes "$DEEZER_WRITE_LOGS") && export DEEZER_WRITE_LOGS
[ -n "$DEEZER_SCHEDULE" ] && DEEZER_SCHEDULE=$(strip_quotes "$DEEZER_SCHEDULE") && export DEEZER_SCHEDULE

# Track if DEEZER_SCHEDULE was explicitly provided (before setting default)
SCHEDULE_PROVIDED=false
if [ -n "$DEEZER_SCHEDULE" ]; then
    SCHEDULE_PROVIDED=true
fi

# Set default schedule if not provided (only needed for cron mode)
if [ -z "$DEEZER_SCHEDULE" ]; then
    DEEZER_SCHEDULE="0 3 * * *"
fi

case "$1" in
    cron)
        setup_cron
        ;;
    run)
        setup_run
        ;;
    shell)
        # Start an interactive shell for debugging
        exec /bin/bash
        ;;
    *)
        # Default behavior: if DEEZER_SCHEDULE was provided, run cron; otherwise run once
        echo "Container started with opts '$1'"
        if [ "$SCHEDULE_PROVIDED" = true ]; then
            setup_cron
        else
            setup_run
        fi
        ;;
esac
