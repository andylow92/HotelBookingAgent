#!/usr/bin/env python3.11
"""Quick test script for the hotel provider agent."""
import uuid
import httpx
import json
import os
import time
import sys

BASE = "http://localhost:8000"

DEFAULT_VARIABLES = [
    {"name": "API_KEY", "value": "hotel-1-key-abc123"},
    {"name": "API_BASE_URL", "value": "https://hacketon-18march-api.orcaplatform.ai/hotel-1"},
    {"name": "MADHACK-ANTHROPIC-KEY", "value": os.getenv("ANTHROPIC_API_KEY", "")},
]

def send_message(message: str, variables: list = None):
    channel = str(uuid.uuid4())
    payload = {
        "thread_id": str(uuid.uuid4()),
        "model": "claude-haiku-4-5-20251001",
        "message": message,
        "conversation_id": 1,
        "response_uuid": str(uuid.uuid4()),
        "message_uuid": str(uuid.uuid4()),
        "channel": channel,
        "variables": variables or DEFAULT_VARIABLES,
        "url": "http://localhost",
    }

    print(f"\n>>> {message}")
    r = httpx.post(f"{BASE}/api/v1/send_message", json=payload, timeout=10)
    r.raise_for_status()

    # Poll for response
    for _ in range(30):
        time.sleep(1)
        poll = httpx.get(f"{BASE}/api/v1/poll/{channel}", timeout=10)
        data = poll.json()
        if data:
            print("<<< Response:")
            print(json.dumps(data, indent=2))
            return data
    print("<<< Timeout waiting for response")

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "What rooms are available?"
    send_message(msg)
