from typing import Any

from app.schemas.query import ExternalSearchResult


def _render_style_rules(style_config: dict[str, Any]) -> str:
    system_prompt = style_config.get("system_prompt")
    if isinstance(system_prompt, str) and system_prompt.strip():
        return system_prompt.strip()

    lines: list[str] = []

    for key in ("tone", "voice"):
        value = style_config.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"{key}: {value.strip()}")

    for key in ("rules", "do", "dont"):
        value = style_config.get(key)
        if isinstance(value, list):
            entries = [str(item).strip() for item in value if str(item).strip()]
            if entries:
                lines.append(f"{key}:")
                lines.extend(f"- {entry}" for entry in entries)

    formatting = style_config.get("formatting")
    if isinstance(formatting, dict) and formatting:
        lines.append("formatting:")
        for key, value in formatting.items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines).strip()


def _build_context(context_chunks: list[dict[str, Any]], query: str) -> str:
    if not context_chunks:
        return "(No relevant documents found for this query.)\n"

    # All chunks are presented as retrieved context — relevance ranking was
    # already performed by the vector search + scoring pipeline.  Splitting
    # into "relevant" vs "weak" based on naive word overlap was causing the
    # LLM to ignore perfectly good chunks that happened to use different
    # vocabulary than the query.
    entries: list[str] = []

    for chunk in context_chunks:
        doc_name = (
            chunk.get("doc_name")
            or chunk.get("doc_title")
            or chunk.get("document_name")
            or chunk.get("title")
            or chunk.get("doc_id")
            or chunk.get("document_id")
            or "unknown-document"
        )
        chunk_id = chunk.get("chunk_id", chunk.get("chunk_idx", "?"))
        entry = f"[{doc_name} | page {chunk.get('page', 'N/A')} | #{chunk_id}]\n{chunk['content']}"
        entries.append(entry)

    return "\n\n-- RETRIEVED CONTEXT --\n\n" + "\n\n".join(entries)


def _build_external_context(external_results: list[ExternalSearchResult]) -> str:
    if not external_results:
        return ""

    sections = ["\n\n-- EXTERNAL KNOWLEDGE (from the internet) --\n"]
    for i, result in enumerate(external_results, 1):
        sections.append(f"\n{i}. {result.title}")
        sections.append(f"   Source: {result.url}")
        sections.append(f"   {result.snippet}")

    return "\n".join(sections)


def build_grounded_prompts(
    query: str,
    context_chunks: list[dict[str, Any]],
    persona_config: dict[str, Any] | None = None,
    external_results: list[ExternalSearchResult] | None = None,
) -> tuple[str, str]:
    context = _build_context(context_chunks, query)
    external_context = _build_external_context(external_results or [])

    system_prompt = """
You are a scientific document assistant.

CORE STRICT RULES:
1. ONLY use the provided context to answer. NEVER use outside knowledge.
2. You MUST identify if the context is ON-TOPIC with the query.
3. Extract + Simplify is allowed. Derivation/Inference is ONLY allowed if context is clearly on-topic.

TOPIC MATCHING (CRITICAL):
- Before answering, determine: Is the context about the same topic as the query?
- If the context discusses the same concepts/subject as the query → on-topic
- If the context is about different topics → off-topic

ANSWER RESTRICTIONS:
- ON-TOPIC context: You may extract, simplify, or clearly infer from it.
- OFF-TOPIC context or NO useful information: You MUST respond EXACTLY:
  "I don't have enough information in the provided documents."

NEVER do these:
- Do NOT make up facts not in the context
- Do NOT explain concepts the context doesn't cover
- Do NOT combine unrelated topics to form an answer
- Do NOT infer beyond what the context directly supports

CITATIONS:
- Always cite using: [document_name | page X | #chunk_id]
- Only use sources that directly contributed

OUTPUT FORMAT (STRICT):
Answer:
<only if context is on-topic, otherwise say insufficient info>

Sources:
- [document_name | page X | #chunk_id]
"""

    if external_results:
        system_prompt += """

EXTERNAL KNOWLEDGE SECTION (if present):
- The external knowledge section provides supplementary information from the internet
- Use this to provide additional context or explanations beyond the documents
- Cite external sources using: [source: URL]
- Distinguish between document-based answers and external knowledge
"""

    if persona_config:
        intensity = persona_config.get("intensity", 0.7)
        persona_name = persona_config.get("name", "a helpful assistant")
        persona_rules = _render_style_rules(persona_config.get("style_config", {}))

        system_prompt += f"""

PERSONA TRANSFORMATION:
After generating the factual answer:
- Rewrite the answer in the style of {persona_name}
- DO NOT change facts or meaning
- DO NOT remove citations
- Keep it clear and natural
- Style intensity: {intensity:.2f}

STYLE RULES:
{persona_rules}
"""

    user_prompt = f"""Context:
{context}{external_context}

Question:
{query}

Follow all rules strictly and produce the final answer."""

    return system_prompt.strip(), user_prompt.strip()


def build_summary_prompt(
    query: str,
    summary_type: str = "document",  # "document", "session", "chapter"
    persona_config: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build prompts for document summarization."""

    system_prompt = """You are a document summarization assistant.

TASK: Create a clear, comprehensive summary.

GUIDELINES:
1. Extract main ideas, key findings, and important details
2. Maintain document structure (Intro → Body → Conclusion)
3. Preserve numerical data, dates, proper nouns
4. Keep it factual - do NOT add outside knowledge
5. Length: ~10-15% of original text

FORMAT:
## Summary
[Concise 2-3 sentence overview]

## Key Points
- [Point 1]
- [Point 2]
...

## Important Details
[Critical data, dates, specifics if any]
"""

    if persona_config:
        intensity = persona_config.get("intensity", 0.7)
        persona_name = persona_config.get("name", "a helpful assistant")
        persona_rules = _render_style_rules(persona_config.get("style_config", {}))
        system_prompt += f"""
PERSONA STYLE:
Rewrite the summary in the style of {persona_name} (intensity: {intensity:.2f}):
{persona_rules}
"""

    user_prompt = f"""Document Context:
{{context}}

Task: {query}

Follow the format above and produce the summary."""

    return system_prompt.strip(), user_prompt.strip()
