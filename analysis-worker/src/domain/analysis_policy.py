SKIP_PATTERNS = frozenset(
    [
        # lock files (all ecosystems)
        ".lock",
        "go.sum",
        # compiled / bytecode
        ".pyc",
        ".class",
        "__pycache__",
        # minified / bundled assets
        ".min.js",
        ".min.css",
        ".bundle.js",
        # build & dependency directories
        "node_modules/",
        "vendor/",
        "dist/",
        "build/",
        "target/",
        # generated code
        ".pb.go",
        "_pb2.py",
        ".generated.",
        "_generated.",
        # test snapshots
        "__snapshots__/",
        ".snap",
        # coverage & CI artefacts
        "lcov.info",
        "coverage.xml",
        ".coverage",
    ]
)

PRIORITY: dict[str, int] = {
    "domain": 0,
    "ports": 0,
    "application": 1,
    "use_cases": 1,
    "infrastructure": 2,
    "interface": 3,
    "api": 3,
    "test": 4,
    "tests": 4,
}


def should_skip(filename: str) -> bool:
    lower = filename.lower()
    return any(p in lower for p in SKIP_PATTERNS)


def file_priority(filename: str) -> int:
    for part in filename.lower().replace("\\", "/").split("/"):
        if part in PRIORITY:
            return PRIORITY[part]
    return 5
