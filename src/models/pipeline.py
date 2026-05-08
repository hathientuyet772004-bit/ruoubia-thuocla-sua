from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PipelineStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class PipelineRun(BaseModel):
    run_id: str
    status: PipelineStatus = PipelineStatus.QUEUED
    sites: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    sites_total: int = 0
    sites_done: int = 0
    products_collected: int = 0
    products_extracted: int = 0
    errors: list[str] = Field(default_factory=list)
    log: list[str] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: Optional[str] = None

    def append_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {msg}")

    def finish(self, status: PipelineStatus = PipelineStatus.DONE) -> None:
        self.status = status
        self.finished_at = datetime.now().isoformat()

    @property
    def progress_pct(self) -> int:
        if self.sites_total == 0:
            return 0
        return int((self.sites_done / self.sites_total) * 100)
