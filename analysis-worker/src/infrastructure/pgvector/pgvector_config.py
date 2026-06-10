EMBED_MAX_ATTEMPTS = 3
EMBED_WAIT_MULTIPLIER = 2.0
EMBED_WAIT_MIN = 1.0
EMBED_WAIT_MAX = 8.0

# Maximum cosine distance (pgvector `<=>`, range 0..2) for a past finding to be
# considered relevant. Matches below this are dropped so a sparse/cold knowledge
# base does not inject unrelated examples into the prompt. Tunable.
SIMILARITY_MAX_DISTANCE = 0.5
