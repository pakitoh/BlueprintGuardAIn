import random
import re

import httpx
import structlog

from src.domain.entities import ReplayProgress
from src.domain.ports.replay_progress_repository import ReplayProgressRepository

logger = structlog.get_logger()

MIN_FILES = 3
MAX_PICK_ATTEMPTS = 10

CURATED_REPOS: list[tuple[str, str]] = [
    ("tiangolo/fastapi", "Python"),
    ("vortico/flama", "Python"),
    ("BurntSushi/ripgrep", "Rust"),
    ("rust-lang/cargo", "Rust"),
    ("grafana/grafana", "Go"),
    ("hashicorp/vault", "Go"),
    ("apache/kafka", "Java"),
    ("elastic/elasticsearch", "Java"),
    ("ktorio/ktor", "Kotlin"),
    ("arrow-kt/arrow", "Kotlin"),
    ("expressjs/express", "JavaScript"),
    ("denoland/deno", "JavaScript"),
    ("redis/redis", "C"),
    ("curl/curl", "C"),
    ("metabase/metabase", "Clojure"),
    ("riemann/riemann", "Clojure"),
]

DEFAULT_REPOS = [
    # Python
    "tiangolo/fastapi",
    "pydantic/pydantic",
    "celery/celery",
    "django/django",
    "pallets/flask",
    # JavaScript / TypeScript
    "vercel/next.js",
    "expressjs/express",
    "vuejs/vue",
    "facebook/react",
    "microsoft/TypeScript",
    # Java
    "spring-projects/spring-boot",
    "elastic/elasticsearch",
    "netty/netty",
    "google/guava",
    "junit-team/junit5",
    # Kotlin
    "square/retrofit",
    "square/okhttp",
    "ktorio/ktor",
    "cashapp/sqldelight",
    "detekt/detekt",
    # Rust
    "tokio-rs/tokio",
    "serde-rs/serde",
    "BurntSushi/ripgrep",
    "hyperium/hyper",
    "rust-lang/cargo",
    # Go
    "gin-gonic/gin",
    "gofiber/fiber",
    "go-chi/chi",
    "docker/compose",
    "hashicorp/terraform",
    # C
    "redis/redis",
    "curl/curl",
    "nginx/nginx",
    "libuv/libuv",
    "git/git",
]


def _parse_last_page(link_header: str) -> int | None:
    match = re.search(r'[?&]page=(\d+)>; rel="last"', link_header)
    return int(match.group(1)) if match else None


async def fetch_next_chronological_commit(
    repo: str,
    token: str,
    progress_repo: ReplayProgressRepository,
    page_cache: dict,
) -> tuple[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    progress = await progress_repo.get(repo)

    async with httpx.AsyncClient() as client:
        if progress is None:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/commits",
                headers=headers,
                params={"per_page": 100, "page": 1},
                timeout=10.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            last_page = _parse_last_page(resp.headers.get("link", "")) or 1
            if last_page == 1:
                page_cache[(repo, 1)] = list(reversed(resp.json()))
            progress = ReplayProgress(
                repository=repo,
                last_page=last_page,
                current_page=last_page,
                page_index=0,
            )

        if progress.current_page < 1:
            raise RuntimeError(f"All commits for {repo} have been replayed")

        cache_key = (repo, progress.current_page)
        if cache_key not in page_cache:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/commits",
                headers=headers,
                params={"per_page": 100, "page": progress.current_page},
                timeout=10.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            page_cache[cache_key] = list(reversed(resp.json()))

        commits = page_cache[cache_key]
        commit = commits[progress.page_index]
        sha = commit["sha"]
        message = commit["commit"]["message"].splitlines()[0]

        next_index = progress.page_index + 1
        if next_index >= len(commits):
            next_progress = ReplayProgress(
                repository=repo,
                last_page=progress.last_page,
                current_page=progress.current_page - 1,
                page_index=0,
            )
        else:
            next_progress = ReplayProgress(
                repository=repo,
                last_page=progress.last_page,
                current_page=progress.current_page,
                page_index=next_index,
            )

        await progress_repo.save(next_progress)
        logger.info(
            "commit_picked_chronological",
            repo=repo,
            sha=sha[:7],
            page=progress.current_page,
            index=progress.page_index,
        )
        return sha, message


async def fetch_commit_diff(repo: str, sha: str, token: str) -> str:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/commits/{sha}",
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
    files = resp.json().get("files", [])
    chunks = []
    for f in files:
        patch = f.get("patch")
        if not patch:
            continue
        chunks.append(
            f"diff --git a/{f['filename']} b/{f['filename']}\n"
            f"--- a/{f['filename']}\n"
            f"+++ b/{f['filename']}\n"
            f"{patch}"
        )
    return "\n".join(chunks)


async def pick_random_commit(token: str) -> tuple[str, str, str]:
    repo = random.choice(DEFAULT_REPOS)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers=headers,
            params={"per_page": 30},
            timeout=10.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        commits = resp.json()
        random.shuffle(commits)
        for commit in commits[:MAX_PICK_ATTEMPTS]:
            sha = commit["sha"]
            detail = await client.get(
                f"https://api.github.com/repos/{repo}/commits/{sha}",
                headers=headers,
                timeout=10.0,
                follow_redirects=True,
            )
            detail.raise_for_status()
            files = detail.json().get("files", [])
            if len(files) >= MIN_FILES:
                message = commit["commit"]["message"].splitlines()[0]
                logger.info("commit_picked", repo=repo, sha=sha[:7], files=len(files))
                return repo, sha, message

    raise RuntimeError(
        f"No commit with >= {MIN_FILES} files found in {repo} "
        f"after {MAX_PICK_ATTEMPTS} attempts"
    )
