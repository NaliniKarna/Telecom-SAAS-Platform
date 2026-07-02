"""Shared response primitives: envelope, pagination, error body."""
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PageMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[object] = None


class ResponseEnvelope(BaseModel, Generic[T]):
    data: Optional[T] = None
    meta: Optional[dict] = None
    errors: list[ErrorDetail] = Field(default_factory=list)
