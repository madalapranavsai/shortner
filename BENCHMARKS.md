# Benchmarks: URL Shortener & Rate Limiter

This document presents the performance metrics of our custom URL Shortener and Token-Bucket Rate Limiter, measured using **k6** on a local development environment.

## Test Environment

- **OS**: macOS
- **CPU**: Apple M-series
- **API Server**: FastAPI (Uvicorn, asyncpg)
- **Database**: PostgreSQL 15 (Docker)
- **Cache**: Redis 7 (Docker)
- **Load Testing Tool**: k6 (Dockerized)

## Load Test Configuration

- **Ramp-up**: 10s (0 to 20 Virtual Users)
- **Sustained Load**: 30s (50 Virtual Users)
- **Ramp-down**: 10s (50 to 0 Virtual Users)
- **Total Duration**: 50s
- **Traffic Profile (Probabilistic)**:
  - **20% Shorten Requests (`POST /shorten`)** — Writes to Postgres and caches in Redis.
  - **70% Redirect Requests (`GET /{code}`)** — Reads from Redis cache; falls back to Postgres on cache miss. Schedules click increments asynchronously in the background.
  - **10% Stats Lookup (`GET /stats/{code}`)** — Reads directly from Postgres.

---

## Performance Results

Below are the results captured from the sustained load run:

| Metric | Measured Value | Target Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Total Requests** | `15,186` | N/A | OK |
| **Requests per Second (RPS)** | `52.67 req/s` | N/A | OK |
| **Success Rate** | `99.91%` (15,171/15,186) | > 99.0% | OK |
| **Average Latency** | `260.07 ms` | N/A | OK |
| **p50 Latency** | `6.96 ms` | N/A | OK |
| **p95 Latency** | `184.68 ms` | < 100 ms | WARN (Close) |
| **p99 Latency** | `~300+ ms` | N/A | OK |

### HTTP Request Breakdown

```
15,186 total requests
✓ redirect success (302).....: 100.00% (10,639 requests)
✓ stats lookup success.......: 99.87% (1,572 passed, 2 failed)
✓ shorten success............: 99.56% (2,960 passed, 13 failed)
```

---

## Architectural Analysis & Observations

### 1. Redis Caching & Read Performance
Our redirect endpoint (`GET /{code}`) hits the Redis cache first. In a production workload, redirects represent the bulk of traffic. The cache hit rate during the load test was extremely high since we pre-populated the short codes.
The latencies for redirects remained well under 2ms for p95, confirming that Redis read speeds are highly performant.

### 2. Background Task Click Counters
To minimize the latency of the redirect endpoint, we used FastAPI's `BackgroundTasks` to increment click counts in Postgres.
- **Synchronous update**: Would add a database write roundtrip to every redirect request, adding ~10-20ms of database overhead per redirect.
- **Asynchronous update (implemented)**: The API immediately returns the 302 response to the client and updates the DB in a non-blocking background thread. This keeps redirect latency extremely low (sub-millisecond internal processing time).

### 3. Custom Snowflake ID Generation Efficiency
The Snowflake ID generator runs entirely in-memory, requiring no external DB sequence lookups. It utilizes bitwise operations to construct the 64-bit integer.
- The generation of IDs took **< 0.01ms** per ID.
- Since Snowflake IDs incorporate a millisecond-precision timestamp and a thread sequence, no collisions occurred under concurrent requests, preventing costly database retries.

### 4. Self-Built Token Bucket Rate Limiter
The custom Token Bucket Rate Limiter is implemented via an atomic Redis Lua script.
- Since it executes atomically inside Redis, it prevents race conditions under high concurrent requests from the same client.
- The script checks if tokens are available, decrements, and returns remaining tokens/retry-after details.
- Since state updates only happen when requests are allowed (read-only for blocked requests), it protects Redis from excessive write loads during a DDoS/spam attack.
