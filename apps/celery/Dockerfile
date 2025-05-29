FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY apps/celery/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Create necessary directories and set permissions
RUN mkdir -p /app/celery_app /app/data /app/logs \
    && chmod 777 /app/data /app/logs

# Copy celery application code to simplified structure
COPY apps/celery/celery.py /app/celery_app/celery.py
COPY apps/celery/tasks.py /app/celery_app/tasks.py
COPY apps/celery/config.py /app/celery_app/config.py
COPY apps/celery/deps.py /app/celery_app/deps.py
COPY apps/celery/__init__.py /app/celery_app/__init__.py
COPY apps/celery/entrypoint.sh /app/entrypoint.sh

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create non-root user for security
RUN groupadd -r celery && useradd -r -g celery celery
RUN chown -R celery:celery /app
USER celery

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]