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
