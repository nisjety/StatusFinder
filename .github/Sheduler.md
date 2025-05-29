# Scheduler Service – Full Implementation Guide

This document walks you through designing, building, and deploying the **Scheduler** service (“gateway”) for the DiscoveryBot platform. It covers:

1. Overview & Responsibilities
2. Architecture & Components
3. Tech Stack & Dependencies
4. API Surface
5. Internal Workflows
6. Caching & Deduplication
7. Scheduling (Celery Beat)
8. Real-time Log Streaming (SSE)
9. Persistence (MongoDB)
10. Configuration & Environment Variables
11. Deployment (Docker Compose)
12. Testing & Validation

---

## 1. Overview & Responsibilities

The **Scheduler** sits at the heart of your crawling platform. It exposes a REST/SSE API to:

* **Enqueue immediate** crawls (return an SSE stream of logs if requested).
* **Schedule future** or **periodic** crawls (return a scheduled job ID).
* **Deduplicate** requests per-user with Redis (return an existing job if parameters match).
* **Persist** job requests, metadata, and results in MongoDB.
* **Dispatch** crawl jobs via Scrapyd (HTTP) using Celery tasks.
* **Stream** real-time log updates back to clients via Server-Sent Events.

---

## 2. Architecture & Components

```text
┌───────────────┐     ┌──────────────┐     ┌─────────────┐
│  Client/UI    │◀───▶│  FastAPI     │◀───▶│   Redis     │
│  (web/mobile) │ SSE │  Scheduler   │     │ (dedupe)    │
└───────────────┘     └─▲────────────┘     └─────────────┘
                         │                    ▲
                         │                    │
                         │                    │
                         ▼                    │
                   ┌───────────┐               │
                   │ MongoDB   │◀──────────────┘
                   │ (jobs)    │
                   └───────────┘
                         │
          schedule /     │    dispatch
        immediate crawl  ▼
                   ┌───────────┐     ┌──────────┐
                   │ RabbitMQ  │◀──▶│  Celery  │
                   │ (broker)  │     │ Worker   │
                   └───────────┘     └──┬───────┘
                                      │
                                      ▼
                                  ┌────────┐
                                  │ Scrapyd│
                                  └────────┘
```

---

## 3. Tech Stack & Dependencies

* **Python 3.10+**
* **FastAPI** – HTTP & SSE API
* **Pydantic** – request / response schemas
* **Celery** – background task queue
* **RabbitMQ** – message broker for Celery
* **Celery Beat** – scheduled task dispatcher
* **MongoDB** – job metadata storage
* **Redis** – high-speed dedupe cache (per-user + TTL)
* **HTTPX / Requests** – talk to Scrapyd
* **Uvicorn** – ASGI server

---

## 4. API Surface

### 4.1 `POST /crawl`

Enqueue or schedule a crawl job.

**Request JSON**

```json
{
  "user_id": "abc123",
  "spider": "seo",
  "start_urls": ["https://example.com"],
  "depth": 2,
  "schedule_at": "2025-06-01T09:00:00Z",      // optional
  "interval": "0 9 * * *",                  // cron (optional)
  "ignore_cache": false,                    // bypass dedupe
  "params": { ... }                         // spider-specific args
}
```

**Responses**

* **200 OK** (immediate or deduped):

  ```json
  { "job_id":"uuid-123","scheduled":false,"cached":true,"cached_at":"…" }
  ```
* **202 Accepted** (future/periodic):

  ```json
  { "job_id":"uuid-456","scheduled":true,"next_run":"2025-06-01T09:00:00Z" }
  ```

### 4.2 `GET /jobs/{job_id}/status`

```json
{ "job_id":"uuid-123", "status":"running", "started_at":"…", "spider_job_id":42 }
```

### 4.3 `GET /jobs/{job_id}/logs` — SSE

* **Content-Type:** `text/event-stream`
* Emits log entries as they arrive:

  ```
  event: log
  data: {"ts":"…","level":"INFO","msg":"Downloading…"}

  event: end
  data: {"status":"finished","spider_job_id":42}
  ```

---

## 5. Internal Workflows

### 5.1 Deduplication Check (Redis)

1. Build key

   ```
   key = f"crawl:{user_id}:{spider}:{sorted(start_urls)}:{depth}:{json.dumps(params,sort_keys=True)}"
   ```
2. If `ignore_cache==false` and `redis.exists(key)` within TTL → **return cached job**.
3. Else → **proceed** to scheduling, then `redis.setex(key, CRAWL_CACHE_TTL, job_id)`.

### 5.2 Immediate vs Scheduled

* **Immediate** (no `schedule_at`/`interval`):
  → push to RabbitMQ via `celery.send_task("enqueue_crawl", args=[job_id,…])`
  → return SSE endpoint URL for real-time logs.

* **Scheduled** (`schedule_at` or `interval` present):
  → register in Celery Beat’s database (or use `add_periodic_task`)
  → respond with a next-run timestamp.

### 5.3 Celery Worker: `enqueue_crawl`

1. Read `job_id, spider, args` from message.
2. Call Scrapyd’s schedule endpoint:

   ```
   POST http://scrapyd:6800/schedule.json
   form: project=DiscoveryBot, spider=seo, …args
   ```
3. Record `scrapyd_job_id` & update MongoDB job status to **running**.
4. Return control; Celery worker exits.

### 5.4 Log Streamer

* **Background task** that polls Scrapyd’s `logs/<spider_job_id>.log` URL (or tail local file).
* Pushes each new line into an internal **Pub/Sub** or Redis list.
* The FastAPI SSE endpoint subscribes clients and streams lines as events.

---

## 6. Caching & Deduplication

* **Layer 1:** Scheduler-level dedupe in Redis (`crawl:{user_id}:…`).
* **Layer 2:** Spider-level HTTP cache in Redis (via custom `RedisCacheStorage` in Scrapy).

Both honor TTLs and both can be bypassed via `ignore_cache`.

---

## 7. Scheduling (Celery Beat)

* Use **database‐backed** Beat scheduler (e.g. `django-celery-beat` or plain Redis).
* On receipt of an `interval` or `cron` in `/crawl`, dynamically register a periodic task

  ```python
  app.add_periodic_task(
      crontab(...), enqueue_crawl.s(job_id, ...),
      name=f"crawl-{job_id}"
  )
  ```
* Store scheduling metadata in MongoDB so you can list/modify/cancel later.

---

## 8. Real-time Log Streaming (SSE)

* **FastAPI** endpoint:

  ```python
  @app.get("/jobs/{job_id}/logs")
  async def stream_logs(job_id: str):
      async def event_generator():
          async for line in redis_pubsub.listen(channel=f"logs:{job_id}"):
              yield f"event: log\ndata: {json.dumps(line)}\n\n"
          yield f"event: end\ndata: done\n\n"
      return StreamingResponse(event_generator(), media_type="text/event-stream")
  ```
* **Celery Worker** or background asyncio task publishes log lines to Redis pubsub as they arrive from Scrapyd.

---

## 9. Persistence (MongoDB)

* **Jobs** collection:

  ```json
  {
    "_id":"uuid-123", "user_id":"…",
    "spider":"seo", "start_urls":[…],
    "depth":2, "params":{…},
    "status":"pending|running|finished|error",
    "scheduled_at":…, "next_run":…, 
    "scrapyd_job_id":42,
    "created_at":…, "updated_at":…
  }
  ```
* **Index** on `(user_id, spider, start_urls, depth, params)` to support fast dedupe lookups.

---

## 10. Configuration & Environment Variables

| Variable                   | Purpose                     | Default               |
| -------------------------- | --------------------------- | --------------------- |
| `MONGO_URI`                | MongoDB connection string   | `mongodb://…`         |
| `REDIS_HOST`, `PORT`, `DB` | Redis for dedupe & pubsub   | `redis:6379,0`        |
| `CRAWL_CACHE_TTL`          | Seconds to cache dedupe key | `3600`                |
| `RABBITMQ_URL`             | Broker for Celery           | `amqp://…`            |
| `SCRAPYD_URL`              | Scrapyd API endpoint        | `http://scrapyd:6800` |
| `LOG_LEVEL`                | Service log verbosity       | `info`                |

---

## 11. Deployment (Docker Compose)

Add to your existing `docker-compose.yml` under `services`:

```yaml
scheduler:
  build: context: .
         dockerfile: scheduler/Dockerfile
  image: discoverybot/scheduler:latest
  environment:
    MONGO_URI: ${MONGO_URI}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    CRAWL_CACHE_TTL: ${CRAWL_CACHE_TTL}
    RABBITMQ_URL: ${RABBITMQ_URL}
    SCRAPYD_URL: ${SCRAPYD_URL}
  depends_on:
    - mongodb
    - redis
    - rabbitmq
    - scrapyd
  ports:
    - "8001:8001"
  networks:
    - discoverybot-network
```

---

## 12. Testing & Validation

1. **Unit Tests**

   * Dedup cache logic: same input → same job\_id; with `ignore_cache` → new job\_id.
   * Pydantic schemas for `/crawl` payload validation.
2. **Integration Tests**

   * Spin up in-memory Redis/Mongo/RabbitMQ (via `pytest-redis`, `mongomock`).
   * Hit `/crawl` endpoint twice, assert dedupe.
   * Hit `/crawl?ignore_cache=true`, assert new scheduling.
   * Consume Celery queue, emulate Scrapyd schedule endpoint, assert DB updates.
3. **Load Tests**

   * Simulate concurrent `/crawl` requests to ensure Redis dedupe holds under load.

---

With this guide you have a complete blueprint for the **Scheduler** service: from API design, through caching and scheduling, to real-time log delivery and deployment.
