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

# Use entrypoint script to handle cron and application
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["default"]
