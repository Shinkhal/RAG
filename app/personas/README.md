## Persona Configs

This directory contains seed persona configuration files.

Each persona JSON file follows this shape:

```json
{
  "persona_id": "einstein",
  "name": "Albert Einstein Style",
  "description": "Short description",
  "is_active": true,
  "style_config": {
    "system_prompt": "Additional prompt instructions applied after factual grounding."
  }
}
```

Current defaults include person-style personas like Einstein, Ronaldo, and Salman Khan.
