from pydantic import BaseModel


class ErrorDetail(BaseModel):
    detail: str
    code: int | None = None
    message: str | None = None
