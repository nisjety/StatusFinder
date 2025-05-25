FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy and install scheduler requirements
COPY scheduler/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONPATH=/app:/app/DiscoveryEngine
ENV PYTHONUNBUFFERED=1
ENV PORT=8001

# Create directories
RUN mkdir -p /app/logs

# Copy entrypoint script
COPY scheduler/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy application code
COPY common/ /app/common/
COPY scheduler/ /app/scheduler/

# Create non-root user
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the scheduler service
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]