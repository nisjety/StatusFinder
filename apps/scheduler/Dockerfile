FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY apps/scheduler/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY apps/scheduler/app/ app/

# Create user for running the application
RUN useradd -m -u 1000 appuser
USER appuser

# Command to start application with specified port
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
