from opentelemetry import metrics

_meter = metrics.get_meter("blueprintguardain.analysis")

code_changes_analyzed = _meter.create_counter(
    name="blueprintguardain_code_changes_analyzed",
    description="Number of code changes analyzed",
    unit="1",
)

analysis_duration = _meter.create_histogram(
    name="blueprintguardain_analysis_duration_seconds",
    description="Time to analyze a code change, from Kafka receive to result published",
    unit="s",
)

embedding_duration = _meter.create_histogram(
    name="blueprintguardain_embedding_duration_seconds",
    description="Time to generate an embedding vector via the LLM provider",
    unit="s",
)

rag_retrieval_duration = _meter.create_histogram(
    name="blueprintguardain_rag_retrieval_duration_seconds",
    description="Time to query pgvector for similar past findings",
    unit="s",
)

rag_similar_count = _meter.create_histogram(
    name="blueprintguardain_rag_similar_findings_count",
    description="Number of similar past findings retrieved per analysis (0 = cold RAG)",
    unit="1",
)

llm_call_duration = _meter.create_histogram(
    name="blueprintguardain_llm_call_duration_seconds",
    description="Latency of a single LLM call attempt",
    unit="s",
)

llm_prompt_tokens = _meter.create_counter(
    name="blueprintguardain_llm_prompt_tokens_total",
    description="Prompt tokens sent to the LLM",
    unit="1",
)

llm_completion_tokens = _meter.create_counter(
    name="blueprintguardain_llm_completion_tokens_total",
    description="Completion tokens received from the LLM",
    unit="1",
)

llm_cost_usd = _meter.create_counter(
    name="blueprintguardain_llm_cost_usd_total",
    description="Estimated USD cost of LLM calls",
    unit="usd",
)
