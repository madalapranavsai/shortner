# Production-Grade URL Shortener & Rate Limiter

A highly performant, production-ready URL Shortener and custom Rate Limiter built with **FastAPI**, **PostgreSQL**, and **Redis** to demonstrate core backend engineering concepts: distributed ID generation, caching strategies with write invalidation, concurrency, and custom rate-limiting algorithms.

---

## Architecture Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as FastAPI Application
    participant Cache as Redis (Cache & Rate Limiter)
    participant DB as Postgres Database

    Client->>API: Request (POST /shorten or GET /{code})
    API->>Cache: Execute Token Bucket Lua Script
    Cache-->>API: Allow / Deny (with Retry-After)
    alt Rate Limit Exceeded
        API-->>Client: 429 Too Many Requests (Retry-After header)
    else Rate Limit OK
        alt POST /shorten
            API->>API: Generate Snowflake ID & Base62 encode
            API->>DB: Insert Short Code & Long URL
            alt Collision Occurred
                API->>API: Retry ID generation (max 3 times)
            end
            API->>Cache: Cache short_code -> long_url
            API-->>Client: 201 Created (short URL)
        else GET /{code}
            API->>Cache: Get long_url for short_code
            alt Cache Hit
                Cache-->>API: Return long_url
            else Cache Miss
                API->>DB: Query URL by short_code
                alt Found in DB
                    DB-->>API: Return url & click_count
                    API->>Cache: Cache short_code -> long_url (TTL)
                else Not Found
                    API-->>Client: 404 Not Found
                end
            end
            API->>DB: Increment click count (Async background task)
            API-->>Client: 302 Redirect to long_url
        end
    end
```

---

## Core Features

1. **Snowflake ID Generation**: Distributed, time-ordered, and decentralized ID generation (no single sequence bottleneck).
2. **Base62 Encoding**: Custom encoder/decoder converting 64-bit Snowflake IDs into compact, web-safe short codes.
3. **Atomic Rate Limiter**: Self-built token-bucket algorithm executed as a Redis Lua script to guarantee thread safety and high performance. Includes customizable limits per API Key and defaults per IP.
4. **Redis Caching & Invalidation**: Reads are cached in Redis. Updates and deletes (`DELETE /{code}`) immediately invalidate (purge) the cache to prevent stale reads.
5. **Asynchronous Click Analytics**: Redirect clicks are written to Postgres asynchronously via FastAPI background tasks, keeping redirect responses sub-millisecond.

---

## Key System Design Decisions & Trade-offs

### 1. Snowflake ID vs. Auto-Incrementing ID
* **Auto-Incrementing ID**:
  * *Pros*: Simple; produces shortest possible codes initially (e.g., ID 1 -> `1`, ID 1000 -> `g8` in Base62).
  * *Cons*: Predictable (easily scrapable); requires a single centralized counter (e.g., Postgres sequence), which forms a scalability bottleneck and single point of failure in distributed multi-instance architectures.
* **Snowflake ID (Implemented)**:
  * *Pros*: Completely decentralized and scales horizontally across up to 1,024 independent worker nodes; guarantees monotonicity and time-ordering.
  * *Cons*: Generates larger integers (64-bit), resulting in longer codes (~10-11 Base62 characters).
  * *Decision*: Chosen to demonstrate modern cloud-native system design patterns. Collision handling is implemented by catching `IntegrityError` and retrying up to 3 times in case of clock drifts.

### 2. Token Bucket (Lua) vs. Sliding Window Rate Limiting
* **Sliding Window**:
  * *Pros*: Highly precise rate limiting; prevents burst abuse right at window boundaries.
  * *Cons*: Very memory intensive (stores a timestamp log for every request in a sorted set).
* **Token Bucket (Implemented)**:
  * *Pros*: High memory efficiency (stores only two numbers: `tokens` and `last_updated` per client); allows controlled bursts of traffic up to the bucket capacity while sustaining a steady average refill rate.
  * *Cons*: Marginally more complex math.
  * *Lua Script Optimization*: Executed as a Lua script in Redis to ensure **atomicity** without lock overhead. To protect Redis during spam attacks, writes only occur when a request is *allowed*; rejected requests bypass Redis writes entirely.

### 3. Asynchronous Click Counting
* **Synchronous Updates**:
  * *Impact*: Adds Postgres write operations (~10-20ms) directly into the redirect HTTP lifecycle.
* **Asynchronous Updates (Implemented)**:
  * *Impact*: The redirect endpoint triggers a FastAPI `BackgroundTask` and immediately returns the HTTP 302 response to the client. The Postgres write occurs out-of-band in a worker pool, lowering p99 latencies to sub-millisecond ranges.

---

## Setup & Running Guide

### Prerequisites
- Docker & Docker Compose
- Python 3.12 (if running locally without Docker)

### Run with Docker Compose
To boot the full application stack (FastAPI web server, Postgres, and Redis):
```bash
docker-compose up --build
```
The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### Run Locally (Development)
1. Initialize virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run database & Redis via Docker:
   ```bash
   docker-compose up -d db cache
   ```
3. Run FastAPI application:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54321/shortner REDIS_URL=redis://localhost:6379/0 WORKER_ID=1 uvicorn app.main:app --reload
   ```

---

## Testing Guide

The test suite contains **unit tests** (for Snowflake/Base62 and Token Bucket limiter) and **integration tests** (testing the entire API lifecycle and cache invalidation).

Ensure the docker databases are running, then execute:
```bash
PYTHONPATH=. .venv/bin/pytest -v
```

---

## Load Testing (k6)

To execute the load test and benchmark the API under heavy concurrent load:
```bash
docker run --rm -i -e BASE_URL=http://host.docker.internal:8000 grafana/k6 run - < k6/load_test.js
```
The load test results are documented in [BENCHMARKS.md](file:///Users/pranavsaimadala/Documents/new/shortner/BENCHMARKS.md).
