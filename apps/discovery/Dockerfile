# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISCOVERY_ENV=production \
    # Playwright specific settings
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install system dependencies and browser dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    gnupg \
    # Required for Playwright browsers
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browser
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium && \
    playwright install-deps

# Install additional dependencies
RUN pip install --no-cache-dir uvloop aiohttp scrapyd-client

# Create required directories
RUN mkdir -p /app/logs /app/eggs /app/dbs /app/items /app/data /etc/scrapyd /screenshots

# Grant permissions for screenshot directory
RUN chown -R root:root /screenshots && chmod 777 /screenshots

# Copy configuration and code
COPY scrapyd.conf /etc/scrapyd/
COPY scrapy.cfg .
COPY setup.py .
COPY discovery ./discovery
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Expose Scrapyd port
EXPOSE 6800

# Define healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -u "${SCRAPYD_USERNAME}:${SCRAPYD_PASSWORD}" http://localhost:6800/daemonstatus.json || exit 1

# Define volumes for persistent data
VOLUME ["/app/logs", "/app/eggs", "/app/dbs", "/app/items", "/app/data", "/screenshots"]

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
