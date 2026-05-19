#!/usr/bin/env python3
# /// script
# dependencies = [
#   "httpx",
#   "faker",
# ]
# ///

# Simulates GitHub webhook calls to the ingestion-service.
#
# Usage:
#   uv run scripts/simulate_webhook.py --count 1
#   uv run scripts/simulate_webhook.py --mode pr --count 3
#   uv run scripts/simulate_webhook.py --local-repo /path/to/repo --count 5
#   uv run scripts/simulate_webhook.py --repo tiangolo/fastapi --count 3   (clones once to cache)

import httpx
import random
import subprocess
import uuid
import time
import argparse
from pathlib import Path
from faker import Faker

fake = Faker()
INGESTION_URL = "http://localhost:8000/webhooks/github"
CLONE_CACHE = Path.home() / ".cache" / "blueprintguardain" / "repos"

# Public Python repos with interesting architecture for realistic findings
DEFAULT_REPOS = [
    "tiangolo/fastapi",
    "encode/starlette",
    "aio-libs/aiokafka",
    "celery/celery",
    "pydantic/pydantic",
]

# Fallback fake data used when no repo source is configured
_FAKE_PATHS = [
    "src/domain/entities.py",
    "src/domain/ports/repository.py",
    "src/domain/ports/event_source.py",
    "src/infrastructure/kafka/consumer.py",
    "src/infrastructure/kafka/producer.py",
    "src/infrastructure/llm/analyzer.py",
    "src/application/use_cases/process_event.py",
    "src/application/use_cases/analyze_change.py",
    "src/interface/api/router.py",
    "tests/application/test_process_event.py",
    "tests/infrastructure/test_kafka_consumer.py",
]

_FAKE_MESSAGES = [
    "Add Kafka consumer for code change events",
    "Refactor domain entities to use frozen dataclasses",
    "Fix dependency injection in analysis use case",
    "Add LLM analyzer port and LiteLLM adapter",
    "Extract repository pattern from service layer",
    "Move business logic from router to use case",
    "Add OpenTelemetry instrumentation to Kafka consumer",
    "Implement pgvector store for past findings",
    "Fix circular import between domain and infrastructure",
    "Add structured logging to analysis worker",
]


# --- Local git helpers ---

def _git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _repo_name(repo_path: Path) -> str:
    """Derive OWNER/REPO from the origin remote URL, or fall back to dir name."""
    try:
        url = _git(repo_path, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
        if "github.com/" in url:
            return url.split("github.com/", 1)[1]
        if "github.com:" in url:
            return url.split("github.com:", 1)[1]
    except subprocess.CalledProcessError:
        pass
    return repo_path.name


def _ensure_cloned(owner_repo: str) -> Path:
    """Return a local path for OWNER/REPO, cloning into cache if needed."""
    dest = CLONE_CACHE / owner_repo.replace("/", "__")
    if not (dest / ".git").exists():
        dest.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{owner_repo}.git"
        print(f"  Cloning {owner_repo} → {dest} (depth 100) ...")
        subprocess.run(
            ["git", "clone", "--depth=100", url, str(dest)],
            check=True,
        )
    return dest


def _parse_name_status(output: str) -> tuple[list[str], list[str], list[str]]:
    added, modified, removed = [], [], []
    for line in output.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts[0][0], parts[1]  # first char covers R100 → R
        if status == "A":
            added.append(path)
        elif status in ("M", "C", "R"):
            modified.append(path)
        elif status == "D":
            removed.append(path)
    return added, modified, removed


def _list_commits(repo_path: Path, n: int = 60) -> list[dict]:
    out = _git(repo_path, "log", "--format=%H\x1f%s", "--no-merges", f"-{n}")
    result = []
    for line in out.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            result.append({"sha": sha.strip(), "subject": subject.strip()})
    return result


def _commit_files(repo_path: Path, sha: str) -> tuple[list[str], list[str], list[str]]:
    out = _git(repo_path, "diff-tree", "--no-commit-id", "-r", "--name-status", sha)
    return _parse_name_status(out)


def _list_merge_commits(repo_path: Path, n: int = 60) -> list[dict]:
    out = _git(repo_path, "log", "--merges", "--format=%H\x1f%s", f"-{n}")
    result = []
    for line in out.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            result.append({"sha": sha.strip(), "subject": subject.strip()})
    return result


def _merge_files(repo_path: Path, sha: str) -> tuple[list[str], list[str], list[str]]:
    out = _git(repo_path, "diff", "--name-status", f"{sha}^1", sha)
    return _parse_name_status(out)


def _pr_title_from_merge_subject(subject: str) -> str:
    """Strip 'Merge pull request #NNN from owner/' boilerplate."""
    if subject.lower().startswith("merge pull request"):
        parts = subject.split(" from ", 1)
        if len(parts) > 1:
            branch = parts[1].split("/", 1)[-1]
            return branch.replace("-", " ").replace("_", " ")
    return subject


# --- Payload builders ---

def build_local_push_payload(
    repo_path: Path, repo_name: str, min_files: int
) -> tuple[dict, dict]:
    commits = _list_commits(repo_path)
    random.shuffle(commits)
    for c in commits:
        added, modified, removed = _commit_files(repo_path, c["sha"])
        if len(added) + len(modified) + len(removed) < min_files:
            continue
        payload = {
            "ref": "refs/heads/main",
            "after": c["sha"],
            "repository": {
                "full_name": repo_name,
                "html_url": f"https://github.com/{repo_name}",
            },
            "commits": [
                {
                    "id": c["sha"],
                    "message": c["subject"],
                    "added": added,
                    "modified": modified,
                    "removed": removed,
                }
            ],
        }
        return payload, {"X-GitHub-Event": "push"}
    raise ValueError(f"No commits with >= {min_files} changed files in {repo_name}")


def build_local_pr_payload(
    repo_path: Path, repo_name: str, min_files: int
) -> tuple[dict, dict]:
    merges = _list_merge_commits(repo_path)
    if not merges:
        raise ValueError(f"No merge commits found in {repo_name} — try --mode push")
    random.shuffle(merges)
    for m in merges:
        added, modified, removed = _merge_files(repo_path, m["sha"])
        if len(added) + len(modified) + len(removed) < min_files:
            continue
        title = _pr_title_from_merge_subject(m["subject"])
        payload = {
            "ref": "refs/heads/main",
            "after": m["sha"],
            "repository": {
                "full_name": repo_name,
                "html_url": f"https://github.com/{repo_name}",
            },
            "commits": [
                {
                    "id": m["sha"],
                    "message": title,
                    "added": added,
                    "modified": modified,
                    "removed": removed,
                }
            ],
        }
        return payload, {"X-GitHub-Event": "push"}
    raise ValueError(
        f"No merge commits with >= {min_files} files in {repo_name} "
        f"(checked {len(merges)})"
    )


def build_fake_push_payload() -> tuple[dict, dict]:
    repo = f"{fake.user_name()}/{fake.word()}-service"
    sha = uuid.uuid4().hex
    paths = random.sample(_FAKE_PATHS, random.randint(2, 5))
    split = random.randint(0, len(paths))
    payload = {
        "ref": f"refs/heads/{random.choice(['main', 'develop', 'feature/kafka', 'fix/domain-leak'])}",
        "after": sha,
        "repository": {
            "full_name": repo,
            "html_url": f"https://github.com/{repo}",
        },
        "commits": [
            {
                "id": sha,
                "message": random.choice(_FAKE_MESSAGES),
                "added": paths[:split],
                "modified": paths[split:],
                "removed": [],
            }
        ],
    }
    return payload, {"X-GitHub-Event": "push"}


# --- Main loop ---

def resolve_repo_sources(
    local_repos: list[str], owner_repos: list[str], no_defaults: bool
) -> list[tuple[Path, str]]:
    """Return list of (repo_path, repo_name) pairs ready for git commands."""
    sources: list[tuple[Path, str]] = []

    for path_str in (local_repos or []):
        p = Path(path_str).expanduser().resolve()
        sources.append((p, _repo_name(p)))

    repos = owner_repos or ([] if no_defaults else DEFAULT_REPOS)
    for owner_repo in repos:
        p = _ensure_cloned(owner_repo)
        sources.append((p, owner_repo))

    return sources


def send_webhook(
    mode: str,
    sources: list[tuple[Path, str]],
    client: httpx.Client,
    min_files: int = 3,
) -> None:
    if sources:
        repo_path, repo_name = random.choice(sources)
        try:
            if mode == "pr":
                payload, headers = build_local_pr_payload(repo_path, repo_name, min_files)
            elif mode == "push":
                payload, headers = build_local_push_payload(repo_path, repo_name, min_files)
            else:  # random
                builder = random.choice([build_local_push_payload, build_local_pr_payload])
                payload, headers = builder(repo_path, repo_name, min_files)
        except Exception as e:
            print(f"  ⚠ Failed to build payload from {repo_name}: {e}")
            return
    else:
        payload, headers = build_fake_push_payload()

    event_type = headers["X-GitHub-Event"]
    repo_name_display = payload["repository"]["full_name"]
    source_label = str(repo_path) if sources else "fake"
    print(f"→ [{time.strftime('%H:%M:%S')}] {event_type} | {repo_name_display}")

    if payload.get("commits"):
        c = payload["commits"][0]
        files = c.get("added", []) + c.get("modified", []) + c.get("removed", [])
        print(f"  msg  : {c['message'][:80]}")
        print(f"  files: ({len(files)}) {', '.join(files[:4])}{'…' if len(files) > 4 else ''}")

    try:
        resp = client.post(INGESTION_URL, json=payload, headers=headers, timeout=5.0)
        mark = "✓" if resp.status_code == 202 else "✗"
        print(f"  {mark} {resp.status_code}")
    except Exception as e:
        print(f"  ✗ {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate GitHub webhooks using local git repos."
    )
    parser.add_argument(
        "--mode", choices=["push", "pr", "random"], default="push",
        help="push = individual commit, pr = merge commit (default: push)",
    )
    parser.add_argument(
        "--local-repo", action="append", dest="local_repos", metavar="PATH",
        help="Path to a local git clone to read commits from (repeatable).",
    )
    parser.add_argument(
        "--repo", action="append", dest="repos", metavar="OWNER/REPO",
        help="GitHub repo to clone into local cache and read from (repeatable). "
             f"Defaults to: {', '.join(DEFAULT_REPOS)}",
    )
    parser.add_argument(
        "--no-default-repos", action="store_true",
        help="Disable the default repo list (requires --local-repo or --repo).",
    )
    parser.add_argument(
        "--min-files", type=int, default=3, metavar="N",
        help="Skip commits/PRs with fewer than N changed files (default: 3).",
    )
    parser.add_argument(
        "--count", type=int,
        help="Number of webhooks to send (default: infinite).",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds between requests (default: 1.0).",
    )
    args = parser.parse_args()

    sources = resolve_repo_sources(
        args.local_repos or [], args.repos or [], args.no_default_repos
    )

    print("=== Webhook Simulator ===")
    print(f"Target    : {INGESTION_URL}")
    print(f"Mode      : {args.mode}")
    if sources:
        for path, name in sources:
            print(f"  repo    : {name}  ({path})")
    else:
        print(f"Source    : fake data")
    print(f"Min files : {args.min_files}")
    print(f"Delay     : {args.delay}s")
    print(f"Count     : {args.count or 'infinite'}")
    print("=========================")

    sent = 0
    with httpx.Client() as client:
        try:
            while True:
                send_webhook(args.mode, sources, client, min_files=args.min_files)
                sent += 1
                if args.count and sent >= args.count:
                    break
                time.sleep(args.delay)
        except KeyboardInterrupt:
            pass

    print(f"\nDone. Sent {sent} webhook(s).")


if __name__ == "__main__":
    main()
