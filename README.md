# FastAPI Webhook Service

A high-performance FastAPI backend service designed to ingest webhook messages, validate signatures, store data idempotently in SQLite, and provide queryable endpoints with metrics.

## Features

- **Webhook Ingestion**: 
  - Validates `X-Hub-Signature-256` HMAC-SHA256 signatures.
  - Idempotent processing based on `message_id`.
  - Strict payload validation (E.164 phone numbers, ISO-8601 UTC timestamps).
- **Data Querying**:
  - Filter messages by sender, timestamp, and text content.
  - Pagination support.
- **Observability**:
  - Structured JSON logging with request IDs.
  - Prometheus metrics (`http_requests_total`, `webhook_requests_total`, `request_latency_ms`).
  - Health check endpoints (`/health/live`, `/health/ready`).
- **Architecture**:
  - Asynchronous SQLite storage (`aiosqlite`).
  - Production-ready Docker container (multi-stage build).
  - Environment-based configuration.

## Setup & Running

### Using Docker (Recommended)

1. **Start the service:**
   ```bash
   make up
   ```
   This builds the image and runs the container on port `8000`.

2. **View logs:**
   ```bash
   make logs
   ```

3. **Stop the service:**
   ```bash
   make down
   ```

### API Usage Examples

**1. GET /health/ready**
Check if the service is ready to accept traffic.
```bash
curl -i http://localhost:8000/health/ready
```

**2. POST /webhook**
To send a message, you must sign the payload.
*Header*: `X-Hub-Signature-256: <hex_digest>`

Python Snippet to generate signature:
```python
import hmac, hashlib
secret = "dev-secret-123"
body = b'{"message_id":"1","from":"+123","to":"+456","ts":"2023-01-01T00:00:00Z"}'
signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
print(signature)
```

**3. GET /messages**
List messages with pagination.
```bash
curl "http://localhost:8000/messages?limit=10&offset=0"
```

## Technical Details

### HMAC Signature Calculation
Security is enforced by validating the `X-Hub-Signature-256` header.
1. Take the **raw** request body bytes.
2. Create an HMAC-SHA256 hash using your `WEBHOOK_SECRET` as the key.
3. The header value should be the hexadecimal digest of the hash (optionally prefixed with `sha256=`).

### Pagination Rules
The `GET /messages` endpoint supports standard limit-offset pagination:
- **`limit`**: The maximum number of records to return. 
  - Default: `50`
  - Minimum: `1`
  - Maximum: `100`
- **`offset`**: The number of records to skip.
  - Default: `0`

### Observability & Metrics
Prometheus metrics are exposed at `/metrics`.

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `http_requests_total` | Counter | `path`, `status` | Total count of HTTP requests processed. |
| `webhook_requests_total` | Counter | `result` (`success`/`duplicate`) | Specific counter for webhook ingestion results. |
| `request_latency_ms` | Histogram | `path`, `status` | Request latency distribution in milliseconds. |

## Configuration

Set the following environment variables (or use `.env`):

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `WEBHOOK_SECRET` | Secret for HMAC signature validation | Yes | - |
| `DATABASE_URL` | Database connection string | Yes | - |
| `LOG_LEVEL` | Logging verbosity | No | `INFO` |

---
**Setup Used: Gemini CLI**# Lyftr-AI-
