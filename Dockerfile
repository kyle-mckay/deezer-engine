# Use Python slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for logs, cache, tmp, and configs
RUN mkdir -p data/logs data/cache data/tmp

# Create a crontab file (can be overridden via DEEZER_SCHEDULE env var)
# Default: run every day at 3 AM UTC
RUN echo "0 3 * * * cd /app && python deezer-engine.py >> /app/data/logs/cron.log 2>&1" > /etc/cron.d/deezer-engine && \
    chmod 0644 /etc/cron.d/deezer-engine && \
    crontab /etc/cron.d/deezer-engine

# Create entrypoint script to manage cron and the application
COPY --chown=root:root docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set environment variable to indicate running in container
ENV CONTAINERIZED=true

# Optional: Set timezone (can be overridden at runtime)
# ENV TZ=UTC

# Environment variables for configuration
# Config overrides (take precedence over config.yml):
# - DEEZER_USER_ID: Deezer user ID
# - DEEZER_ARL_TOKEN: Deezer ARL authentication token
# - DEEZER_BATCH_SIZE: Batch size for API operations (default: 50)
# - DEEZER_LOG_LEVEL: Log level - DEBUG, INFO, WARNING, ERROR (default: INFO)
# - DEEZER_WRITE_LOGS: Write logs to file - true/false (default: true)
# - DEEZER_SCHEDULE: Cron schedule expression (default: "0 3 * * *" for daily at 3 AM UTC)
# - TZ: Timezone for cron (e.g., "ETC/UTC")
# - DEEZER_PRINT_BANNER: Print banner on startup - true/false (default: true)
# - DEEZER_PLAYLIST_CAP: The maximum number of songs that can be put into a playlist (default: 5000)
# - DEEZER_FAVORITES_CAP: The maximum number of songs that can be put into your favorites (default: 10000)

# Use entrypoint script to handle cron and application
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["default"]
