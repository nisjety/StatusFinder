# DiscoveryBot Scheduler

The Scheduler service is a FastAPI-based component of the DiscoveryBot project responsible for managing crawl requests, scheduling, and monitoring.

## Features

- **Immediate and scheduled crawling**: Run crawl jobs immediately or schedule them for later execution
- **Deduplication**: Avoid duplicate crawls of the same URLs within a configurable time window
- **Caching**: Cache crawl results for faster responses
- **Real-time monitoring**: Stream job logs using Server-Sent Events (SSE)
- **Recurring jobs**: Support for cron-style recurring crawl jobs

## Architecture

The Scheduler service consists of:

- **FastAPI application**: REST API for job submission and monitoring
- **Celery workers**: Background task processing for job enqueueing and monitoring
- **MongoDB**: Job metadata and results storage
- **Redis**: Caching and real-time logs streaming
- **RabbitMQ**: Message broker for Celery tasks
- **Scrapyd**: Crawler execution service

## API Endpoints

### POST `/api/v1/crawl`

Submit a new crawl request or schedule one for later execution.

**Request body:**
```json
{
  "user_id": "user-123",
  "spider": "quick",
  "start_urls": ["https://example.com"],
  "depth": 1,
  "schedule_at": null,
  "interval": null,
  "ignore_cache": false,
  "params": {
    "custom_settings": {
      "DOWNLOAD_DELAY": 2
    }
  }
}
```

**Response (immediate execution):**
```json
{
  "job_id": "f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8",
  "status": "running",
  "created_at": "2025-05-26T14:30:00.000Z",
  "updated_at": "2025-05-26T14:30:00.000Z",
  "cached": false,
  "logs_url": "/api/v1/jobs/f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8/logs"
}
```

**Response (scheduled execution):**
```json
{
  "job_id": "f5f9a8d3-f4e9-4a1e-8e3a-b9c4e5f6a7b8",
  "status": "scheduled",
  "created_at": "2025-05-26T14:30:00.000Z",
  "updated_at": "2025-05-26T14:30:00.000Z",
  "schedule_at": "2025-05-26T18:00:00.000Z",
  "interval": "0 */6 * * *"
}
```

### GET `/api/v1/jobs/{job_id}`

Get the status of a specific job.

**Response:**
Same as the POST response.

### GET `/api/v1/jobs/{job_id}/logs`

Stream logs for a specific job using Server-Sent Events.

**Events:**
- `log`: Log message event
- `heartbeat`: Keep-alive event
- `complete`: Job completion event

## Setup and Configuration

### Environment Variables

| Name | Description | Default |
|------|-------------|---------|
| MONGO_URI | MongoDB connection URI | mongodb://localhost:27017/discovery |
| MONGO_DB_NAME | MongoDB database name | discovery |
| REDIS_HOST | Redis host | localhost |
| REDIS_PORT | Redis port | 6379 |
| REDIS_DB | Redis database index | 0 |
| REDIS_PASSWORD | Redis password | None |
| RABBITMQ_URI | RabbitMQ connection URI | amqp://guest:guest@localhost:5672// |
| SCRAPYD_URL | Scrapyd API endpoint URL | http://localhost:6800 |
| SCRAPYD_PROJECT | Scrapyd project name | discovery |
| CRAWL_CACHE_TTL | Time-to-live for crawl cache in seconds | 3600 |
| API_PREFIX | API route prefix | /api/v1 |
| DEBUG | Debug mode flag | False |

## Development

### Local Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Start the FastAPI application:

```bash
uvicorn app.main:app --reload
```

3. Start Celery worker:

```bash
celery -A app.tasks.celery worker --loglevel=info
```

4. Start Celery beat (for scheduled tasks):

```bash
celery -A app.tasks.celery beat --loglevel=info
```

### Docker Setup

Use Docker Compose to start all services:

```bash
docker-compose up -d
```

## Testing

The application uses pytest for unit and integration testing. The test suite includes:

- Mock-based testing with fakeredis, mongomock, and respx
- Deduplication testing (same requests produce same job ID)
- Cache bypass testing (ignore_cache=True produces a new job)
- SSE log streaming testing
- Celery task testing with mocks

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage reporting
pytest --cov=app

# Run specific test files
pytest tests/test_crawl.py
pytest tests/test_tasks.py
pytest tests/test_models.py
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.
