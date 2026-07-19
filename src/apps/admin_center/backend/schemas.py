from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic import model_validator

from apps.admin_center.backend.cron_schedule import parse_cron


class SourceSchema(BaseModel):
    name: str
    url: str
    type: str
    category: str
    note: str | None = None
    store_scope: Literal["site", "product", "branch", "marketplace"] = "site"
    store_name: str | None = None
    store_url: str | None = None
    store_address: str | None = None
    store_phone: str | None = None
    store_channel: Literal["online", "physical", "hybrid"] | None = None
    store_locator_url: str | None = None
    auto_promote_rules: bool = True
    quality_gate_enabled: bool = True
    important: bool = False


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


class SyntheticDataGenerateSchema(BaseModel):
    row_count: int = Field(default=20, ge=1, le=200)
    product_types: list[str] = Field(default_factory=list)
    reference_sources: list[str] = Field(default_factory=list)
    region: str = Field(default="Toàn quốc", max_length=120)
    output_columns: list[str] = Field(default_factory=list)
    generation_mode: Literal["synthetic", "grounded_synthetic"] = "synthetic"
    persist: bool = False


class SyntheticBatchDecisionSchema(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


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

    @model_validator(mode="after")
    def validate_automatic_pipeline(self):
        if not self.source_ids:
            raise ValueError("pipeline must include at least one source_id")
        if self.schedule_type == "cron":
            if not self.cron:
                raise ValueError("cron expression is required for cron schedule")
            parse_cron(self.cron)
        return self


class DedupDecisionSchema(BaseModel):
    status: str
    note: str | None = None


class LoginSchema(BaseModel):
    password: str


class GenerationPromptSchema(BaseModel):
    content: str
