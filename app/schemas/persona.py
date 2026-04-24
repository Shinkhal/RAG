from datetime import datetime

from pydantic import BaseModel, Field


class StyleConfig(BaseModel):
    system_prompt: str = Field(min_length=20)


class PersonaCreateRequest(BaseModel):
    persona_id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    style_config: StyleConfig
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    sample_responses: list[dict] | None = None
    is_active: bool = True
    version: int = Field(default=1, ge=1)


class PersonaUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    style_config: StyleConfig | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    sample_responses: list[dict] | None = None
    is_active: bool | None = None
    version: int | None = Field(default=None, ge=1)


class PersonaResponse(BaseModel):
    persona_id: str
    name: str
    description: str | None
    style_config: dict
    intensity: float
    sample_responses: list[dict] | None
    is_active: bool
    is_system: bool
    created_by: str | None
    version: int
    created_at: datetime
    updated_at: datetime
