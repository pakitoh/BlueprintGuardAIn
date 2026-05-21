import random
import httpx
import structlog

logger = structlog.get_logger()

MIN_FILES = 3
MAX_PICK_ATTEMPTS = 10

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
        f"No commit with >= {MIN_FILES} files found in {repo} after {MAX_PICK_ATTEMPTS} attempts"
    )
