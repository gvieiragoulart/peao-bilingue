from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SearchCreate(BaseModel):
    name: str = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    exclude: list[str] = []
    active: bool = True

    @field_validator("keywords", "exclude")
    @classmethod
    def sem_termos_vazios(cls, termos: list[str]) -> list[str]:
        limpos = [termo.strip() for termo in termos if termo.strip()]
        if not limpos and termos:
            raise ValueError("termos não podem ser só espaços")
        return limpos


class SearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    keywords: list[str] | None = Field(default=None, min_length=1)
    exclude: list[str] | None = None
    active: bool | None = None


class SearchRead(BaseModel):
    id: int
    name: str
    keywords: list[str]
    exclude: list[str]
    active: bool
    created_at: datetime
