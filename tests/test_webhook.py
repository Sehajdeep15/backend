import hmac, hashlib, requests, json

url = "http://localhost:8000/webhook"
secret = "testsecret"
payload = {
    "message_id": "m1",
    "from": "+911234567890",
    "to": "+14155550100",
    "ts": "2025-01-15T10:00:00Z",
    "text": "Hello"
}
# Use separators to ensure no spaces in JSON for signature consistency
body = json.dumps(payload, separators=(',', ':'))
signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Hub-Signature-256": signature
}

print(f"Payload: {body}")
print(f"Signature: {signature}")

try:
    response = requests.post(url, data=body, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
