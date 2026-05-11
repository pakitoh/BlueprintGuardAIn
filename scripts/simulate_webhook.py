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
import time
import argparse
from faker import Faker

# This script simulates GitHub webhook calls to the ingestion-service with randomized data.
# Usage:
#   uv run scripts/simulate_webhook.py --mode [push|pr|random] --count [N] --delay [SECONDS]

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
        "ref": f"refs/heads/{random.choice(['main', 'develop', 'feature-ai', 'hotfix-bug'])}",
        "after": uuid.uuid4().hex,
        "repository": repo
    }, {"X-GitHub-Event": "push"}

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
    }, {"X-GitHub-Event": "pull_request"}

def send_webhook(mode: str):
    if mode == "push":
        payload, headers = generate_push_payload()
    elif mode == "pr":
        payload, headers = generate_pr_payload()
    else: # random
        payload, headers = random.choice([generate_push_payload, generate_pr_payload])()

    event_type = headers["X-GitHub-Event"]
    
    print(f"🚀 [{time.strftime('%H:%M:%S')}] Simulating {event_type}...")
    
    try:
        response = httpx.post(BASE_URL, json=payload, headers=headers, timeout=5.0)
        status_color = "✅" if response.status_code == 202 else "⚠️"
        print(f"{status_color} Status: {response.status_code} | Repo: {payload['repository']['full_name']}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Simulate GitHub webhooks with random data.")
    parser.add_argument("--mode", choices=["push", "pr", "random"], default="random", help="Type of event to simulate")
    parser.add_argument("--count", type=int, help="Number of requests to send (omit to run indefinitely)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds (default: 1.0)")
    
    args = parser.parse_args()

    print(f"--- Webhook Simulator Started ---")
    print(f"Target: {BASE_URL}")
    print(f"Mode: {args.mode}")
    print(f"Delay: {args.delay}s")
    if args.count:
        print(f"Count: {args.count} requests")
    else:
        print(f"Running indefinitely... (Ctrl+C to stop)")
    print(f"---------------------------------")

    sent = 0
    try:
        while True:
            send_webhook(args.mode)
            sent += 1
            
            if args.count and sent >= args.count:
                print(f"\nFinished sending {args.count} requests.")
                break
                
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print(f"\nStopped by user. Total sent: {sent}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
