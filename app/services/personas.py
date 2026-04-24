import json
from pathlib import Path

from app.db.database import async_session
from app.db.models import Persona
from app.repositories.supabase_repo import SupabaseRepo


def _persona_config_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "personas" / "configs"


def _load_persona_files() -> list[dict]:
    persona_dir = _persona_config_dir()
    persona_payloads: list[dict] = []

    for file_path in sorted(persona_dir.glob("*.json")):
        if file_path.name == "personas.json":
            continue
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        persona_payloads.append(payload)

    return persona_payloads


def build_persona_prompt_config(persona: Persona, intensity: float | None = None) -> dict:
    resolved_intensity = persona.intensity if intensity is None else intensity
    return {
        "persona_id": persona.persona_id,
        "name": persona.name,
        "intensity": resolved_intensity,
        "style_config": persona.style_config or {},
    }


async def ensure_default_personas() -> None:
    payloads = _load_persona_files()
    if not payloads:
        return

    async with async_session() as session:
        repo = SupabaseRepo(session)
        for payload in payloads:
            persona_id = payload.get("persona_id")
            name = payload.get("name")
            style_config = payload.get("style_config") or {}
            # Backward-compatible fallback if configs provide only top-level system_prompt.
            if not style_config and payload.get("system_prompt"):
                style_config = {"system_prompt": payload["system_prompt"]}

            if not persona_id or not name or not style_config:
                continue

            existing = await repo.get_persona(persona_id, include_inactive=True)
            if existing:
                continue

            persona = Persona(
                persona_id=persona_id,
                name=name,
                description=payload.get("description"),
                style_config=style_config,
                intensity=payload.get("intensity", 0.7),
                sample_responses=payload.get("sample_responses"),
                is_active=payload.get("is_active", True),
                is_system=payload.get("is_system", True),
                created_by=payload.get("created_by", "system"),
                version=payload.get("version", 1),
            )
            await repo.create_persona(persona)
