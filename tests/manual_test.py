import os
import hashlib
import hmac
import json
import sys
import asyncio
import aiosqlite
# import pytest # Not available
from fastapi.testclient import TestClient

# Set env before importing app
os.environ["WEBHOOK_SECRET"] = "secret123"
os.environ["DATABASE_URL"] = "sqlite:///test_messages.db"

from app.main import app, storage

client = TestClient(app)

def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

import asyncio

def setup_db():
    storage.db_path = "test_messages.db"
    # storage.init_db is async, but manual_test.py setup_db is called synchronously in main.
    # We'll use asyncio.run or similar.
    asyncio.run(storage.init_db())
    # Clean up
    async def clear_db():
        async with aiosqlite.connect(storage.db_path) as db:
            await db.execute("DELETE FROM messages")
            await db.commit()
    asyncio.run(clear_db())

def cleanup():
    if os.path.exists("test_messages.db"):
        os.remove("test_messages.db")

def test_webhook_success():
    print("Running test_webhook_success...", end=" ")
    payload = {
        "message_id": "msg1",
        "from": "+1234567890",
        "to": "+0987654321",
        "ts": "2023-10-27T10:00:00Z",
        "text": "Hello World"
    }
    body = json.dumps(payload).encode()
    signature = sign_payload(body, "secret123")
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert response.json() == {"status": "ok"}
    
    # Check stats
    response = client.get("/stats")
    assert response.json()["total_messages"] == 1
    print("PASS")

def test_webhook_duplicate():
    print("Running test_webhook_duplicate...", end=" ")
    payload = {
        "message_id": "msg1", # Same ID as success
        "from": "+1234567890",
        "to": "+0987654321",
        "ts": "2023-10-27T10:00:00Z",
        "text": "Hello World"
    }
    body = json.dumps(payload).encode()
    signature = sign_payload(body, "secret123")
    
    # First insert might be from previous test if db not cleared, but let's just try insert again
    response = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": signature})
    assert response.status_code == 200
    
    # Still 1 message (assuming previous test ran)
    response = client.get("/stats")
    assert response.json()["total_messages"] == 1
    print("PASS")

def test_webhook_invalid_signature():
    print("Running test_webhook_invalid_signature...", end=" ")
    payload = {"message_id": "msg2", "from": "+1", "to": "+2", "ts": "2023-01-01T00:00:00Z"}
    body = json.dumps(payload).encode()
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": "wrongsignature"}
    )
    assert response.status_code == 401
    print("PASS")

def test_webhook_invalid_payload():
    print("Running test_webhook_invalid_payload...", end=" ")
    # Missing message_id
    payload = {"from": "+1", "to": "+2", "ts": "2023-01-01T00:00:00Z"}
    body = json.dumps(payload).encode()
    signature = sign_payload(body, "secret123")
    
    response = client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature}
    )
    assert response.status_code == 422
    print("PASS")

def test_get_messages_filter():
    print("Running test_get_messages_filter...", end=" ")
    setup_db() # Clear DB for this test
    
    # Insert two messages
    m1 = {"message_id": "1", "from": "+111", "to": "+999", "ts": "2023-01-01T10:00:00Z", "text": "foo"}
    m2 = {"message_id": "2", "from": "+222", "to": "+999", "ts": "2023-01-02T10:00:00Z", "text": "bar"}
    
    for m in [m1, m2]:
        body = json.dumps(m).encode()
        sig = sign_payload(body, "secret123")
        client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})
        
    # Filter by from
    response = client.get("/messages?from=%2B111")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["message_id"] == "1"
    
    # Filter by since
    response = client.get("/messages?since=2023-01-02T00:00:00Z")
    data = response.json()["data"]
    assert len(data) == 1, f"Expected 1, got {len(data)}"
    assert data[0]["message_id"] == "2"
    print("PASS")

def test_health_metrics():
    print("Running test_health_metrics...", end=" ")
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200 
    
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "webhook_requests_total" in metrics.text
    print("PASS")

if __name__ == "__main__":
    try:
        setup_db()
        test_webhook_success()
        test_webhook_duplicate()
        test_webhook_invalid_signature()
        test_webhook_invalid_payload()
        test_get_messages_filter()
        test_health_metrics()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()
