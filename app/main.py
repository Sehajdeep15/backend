import hmac
import hashlib
import re
from datetime import datetime
from typing import Optional, List

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.storage import Storage
from app.logging_utils import setup_logging, RequestLogMiddleware
from app.metrics import record_http_request, record_webhook_result, render_metrics
from app.models import WebhookMessageIn, WebhookResponse, MessageOut, MessagesListResponse, StatsResponse

# Initialize Logging
setup_logging(settings.LOG_LEVEL)

# Initialize Storage
storage = Storage(settings.DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await storage.init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Middleware
app.add_middleware(RequestLogMiddleware)

# --- Dependencies ---

async def verify_signature(request: Request):
    if not settings.WEBHOOK_SECRET:
         # If secret not set, maybe fail safe or skip? 
         # Requirements say "Validate ... using env". Implies env must be set.
         # Logic for /health/ready says 503 if secret not set.
         # So here we should probably fail if not set or if sig missing.
         raise HTTPException(status_code=503, detail="Server configuration error")

    signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256")
    # or strict requirement for specific header? usually standard.
    # User specified X-Signature in their request.
    
    if not signature:
         # Let's try to be flexible? No, strict validation.
         # I'll use a generic error for now if header is missing.
         # Actually, better to check signature if present, else 401.
         pass # Handled below
    
    body = await request.body()
    
    # Compute signature
    # Signature usually format "sha256=<hex>" or just "<hex>"
    # I'll assume just hex or handle "sha256=" prefix.
    
    if not signature:
         raise HTTPException(status_code=401, detail="invalid signature")

    # simplified handling: assume header is just the hex digest or sha256=digest
    sig_hash = signature
    if signature.startswith("sha256="):
        sig_hash = signature.split("=")[1]
        
    expected_hash = hmac.new(
        key=settings.WEBHOOK_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(sig_hash, expected_hash):
        raise HTTPException(status_code=401, detail="invalid signature")

# --- Routes ---

@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
    request: Request,
    payload: WebhookMessageIn, 
):
    # Verify signature first
    await verify_signature(request)
    
    # Store message_id in state for logging
    request.state.message_id = payload.message_id
    
    # Idempotent insert
    inserted = await storage.insert_message(
        message_id=payload.message_id,
        sender=payload.sender,
        receiver=payload.receiver,
        ts=payload.ts,
        text=payload.text
    )
    
    # Store dup status
    is_dup = not inserted
    request.state.dup = is_dup
    request.state.result = "ok" # result field for logging
    
    record_webhook_result("duplicate" if is_dup else "success")
    
    return WebhookResponse(status="ok")

@app.get("/messages", response_model=MessagesListResponse)
async def get_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = 0,
    from_: Optional[str] = Query(None, alias="from"),
    since: Optional[datetime] = None,
    q: Optional[str] = None
):
    data, total = await storage.query_messages(limit, offset, from_, since, q)
    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    return await storage.compute_stats()

@app.get("/health/live")
def health_live():
    return {"status": "alive"}

@app.get("/health/ready")
async def health_ready():
    db_ok = await storage.check_connection()
    secret_ok = bool(settings.WEBHOOK_SECRET)
    
    if db_ok and secret_ok:
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Not ready")

@app.get("/metrics")
def get_metrics():
    return PlainTextResponse(render_metrics())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

