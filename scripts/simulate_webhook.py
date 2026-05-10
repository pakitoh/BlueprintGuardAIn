#!/usr/bin/env python3
# /// script
# dependencies = [
#   "httpx",
#   "faker",
# ]
# ///

import httpx
import sys
import json
import random
import uuid
from faker import Faker

# This script can be run with: uv run scripts/simulate_webhook.py [push|pr]
# It simulates a GitHub webhook call to the ingestion-service with randomized data.

fake = Faker()
BASE_URL = "http://localhost:8000/webhooks/github"

def generate_repository():
    name = fake.word()
    user = fake.user_name()
    full_name = f"{user}/{name}"
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}"
    }

def generate_push_payload():
    repo = generate_repository()
    return {
        "ref": f"refs/heads/{random.choice(['main', 'develop', 'feature-ai'])}",
        "after": uuid.uuid4().hex,
        "repository": repo
    }

def generate_pr_payload():
    repo = generate_repository()
    pr_number = random.randint(1, 1000)
    return {
        "action": random.choice(["opened", "synchronize", "reopened"]),
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "title": fake.sentence(nb_words=6),
            "head": {"sha": uuid.uuid4().hex},
            "base": {"repo": repo}
        },
        "repository": repo
    }

def simulate(event_type: str):
    if event_type == "push":
        payload = generate_push_payload()
        headers = {"X-GitHub-Event": "push"}
    elif event_type == "pr":
        payload = generate_pr_payload()
        headers = {"X-GitHub-Event": "pull_request"}
    else:
        print(f"Unknown event type: {event_type}. Use 'push' or 'pr'.")
        sys.exit(1)

    print(f"🚀 Simulating {event_type} event...")
    print(f"📦 Repository: {payload['repository']['full_name']}")
    if event_type == "push":
        print(f"🔗 Ref: {payload['ref']} | SHA: {payload['after'][:8]}")
    else:
        print(f"🔗 PR #{payload['number']}: {payload['pull_request']['title']}")

    try:
        response = httpx.post(BASE_URL, json=payload, headers=headers)
        print(f"✅ Status Code: {response.status_code}")
        print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nIs the ingestion-service running on http://localhost:8000?")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "push"
    simulate(mode)
