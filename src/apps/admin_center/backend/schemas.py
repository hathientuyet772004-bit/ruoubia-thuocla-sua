from __future__ import annotations

from pydantic import BaseModel, Field


class SourceSchema(BaseModel):
    name: str
    url: str
    type: str
    category: str
    note: str | None = None


class ExtractionFieldSchema(BaseModel):
    name: str
    selector: str = ""
    attr: str | None = None
    required: bool = False
    transform: str | None = None


class ExtractionPreviewSchema(BaseModel):
    target: str = "product_detail"
    fields: list[ExtractionFieldSchema] = Field(default_factory=list)
    raw_artifact_id: str | None = None


class ExtractionRulePatchSchema(ExtractionPreviewSchema):
    expected_version: str | None = None


class DedupDecisionSchema(BaseModel):
    status: str
    note: str | None = None


class LoginSchema(BaseModel):
    password: str
