import logging
import json
import time
import uuid
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import contextvars

from app.metrics import record_http_request

REQUEST_ID_CTX_KEY = "request_id"
_request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(REQUEST_ID_CTX_KEY, default=None)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            log_record = record.msg.copy()
        else:
            log_record = {"message": record.getMessage()}

        if "ts" not in log_record:
            log_record["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        if "level" not in log_record:
            log_record["level"] = record.levelname

        if "request_id" not in log_record:
            rid = _request_id_ctx_var.get()
            if rid:
                log_record["request_id"] = rid

        return json.dumps(log_record)

def setup_logging(log_level: str):
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = _request_id_ctx_var.set(request_id)
        
        start_time = time.time()
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            
            log_payload = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": "INFO",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": round(latency_ms, 2)
            }
            
            if request.url.path == "/webhook":
                if hasattr(request.state, "message_id"):
                    log_payload["message_id"] = request.state.message_id
                if hasattr(request.state, "dup"):
                    log_payload["dup"] = request.state.dup
                if hasattr(request.state, "result"):
                    log_payload["result"] = request.state.result

            logging.getLogger("access").info(log_payload)
            record_http_request(request.url.path, status_code, latency_ms)
            _request_id_ctx_var.reset(token)