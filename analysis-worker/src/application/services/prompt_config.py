PROMPT_VERSION = "0.1"

MAX_VALIDATION_RETRIES = 2

RETRY_EMPTY_FINDINGS = (
    "\n\nYour previous response contained no findings. "
    "The diff is non-trivial — please re-examine it and provide at least one architectural observation."
)

RETRY_DUPLICATE_FINDINGS = (
    "\n\nYour previous response contained redundant findings. "
    "Please consolidate overlapping observations into distinct, non-repeating points."
)

PATCH_BUDGET = 12_000  # ~3k tokens; leaves room for RAG context and model response

SYSTEM_ROLE = "You are an expert software architect reviewing a code change."

INSTRUCTIONS = (
    "Provide a concise list of architectural observations, one per line. "
    "Focus on design patterns, potential issues, coupling, and anything worth flagging in a code review."
)

NO_PATCH_PLACEHOLDER = "  (no patch available)"

NONE_LISTED_PLACEHOLDER = "  (none listed)"

SIZE_WARNING = (
    "\n⚠ {count} file(s) excluded — PR may be too large for full review. "
    "Consider splitting the change. Excluded: {files}\n"
)

PAST_FINDINGS_HEADER = "Similar past findings for reference:"

PROMPT_TEMPLATE = (
    "{system_role}\n\n"
    "Repository: {repository}\n"
    "Event: {event_type}\n"
    "Branch: {ref}\n"
    "SHA: {sha}\n\n"
    "Commit messages:\n{messages_section}\n\n"
    "Changed files (diff):\n{patch_section}"
    "{size_note}"
    "{examples_section}"
    "\n{instructions}"
)
