FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY celery/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY common/ /app/common/
COPY celery/ /app/celery/
COPY Discovery/ /app/Discovery/

# Create necessary directories
RUN mkdir -p /app/logs /app/celery/beat

# Set Python path
ENV PYTHONPATH="/app:/app/celery:/app/common"

# Copy entrypoint script
COPY celery/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set working directory to celery for proper imports
WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]