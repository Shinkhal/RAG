from typing import Any


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

    query_words = {w.lower() for w in query.split() if len(w) > 2}
    relevant: list[str] = []
    weak: list[str] = []

    for chunk in context_chunks:
        chunk_text = chunk["content"].lower()
        overlap = query_words & {w for w in chunk_text.split() if len(w) > 3}
        entry = f"[{chunk['doc_name']} | page {chunk.get('page', 'N/A')} | #{chunk.get('chunk_id', '?')}]\n{chunk['content']}"
        if overlap:
            relevant.append(entry)
        else:
            weak.append(entry)

    sections = []
    if relevant:
        sections.append("\n\n-- RELEVANT CONTEXT --\n\n" + "\n\n".join(relevant))
    if weak:
        sections.append("\n\n-- WEAK CONTEXT (may not be on-topic) --\n\n" + "\n\n".join(weak))

    return "\n\n".join(sections)

def build_grounded_prompts(
    query: str,
    context_chunks: list[dict[str, Any]],
    persona_config: dict[str, Any] | None = None,
) -> tuple[str, str]:
    context = _build_context(context_chunks, query)

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
{context}

Question:
{query}

Follow all rules strictly and produce the final answer."""

    return system_prompt.strip(), user_prompt.strip()