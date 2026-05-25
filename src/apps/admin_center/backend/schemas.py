from __future__ import annotations

from typing import Literal

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


class GeminiExtractionAnalyzeSchema(BaseModel):
    domain: str
    raw_artifact_id: str | None = None
    html: str | None = None
    url: str | None = None
    page_type: str | None = None
    target_hint: str | None = None


class AIReviewGenerateSchema(BaseModel):
    domain: str
    raw_artifact_id: str | None = None
    html: str | None = None
    url: str | None = None
    page_type: str | None = None
    target_hint: str | None = None
    max_items: int = 24


class AIReviewDecisionSchema(BaseModel):
    status: Literal["pending", "needs_review", "approved", "rejected"]
    note: str | None = None


class PipelineSchema(BaseModel):
    name: str
    description: str | None = None
    mode: Literal["crawler", "hybrid", "ai"] = "hybrid"
    source_ids: list[str] = Field(default_factory=list)
    entry_urls: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    target_hints: list[str] = Field(default_factory=list)
    schema_mode: Literal["auto", "guided"] = "auto"
    schedule_type: Literal["manual", "cron"] = "manual"
    cron: str | None = None
    page_budget: int = 100
    max_depth: int = 2
    retry_attempts: int = 3
    retry_backoff_seconds: float = 1.5
    browser_fallback: bool = False
    region: str | None = "VN"
    user_agent: str | None = None
    enabled: bool = True
    notes: str | None = None


class DedupDecisionSchema(BaseModel):
    status: str
    note: str | None = None


class LoginSchema(BaseModel):
    password: str
