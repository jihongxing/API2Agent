from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class UsageEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    routing_decision_id: str | None = None
    execution_mode: Literal["direct", "proxy", "shadow", "replay"] = "proxy"
    project_id: str
    capability_id: str
    provider_id: str
    tool_id: str
    method: str
    path: str
    status_code: int | None = None
    success: bool = False
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    error_type: str | None = None
    request_metadata: dict[str, Any] | None = None
    credential_reference: str | None = None
    provider_runtime_reference: str | None = None
    is_golden: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageSummary(BaseModel):
    project_id: str | None = None
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    estimated_cost: float = 0.0
    error_counts: dict[str, int] = Field(default_factory=dict)


class UsageLedgerRow(BaseModel):
    project_id: str
    capability_id: str
    provider_id: str
    execution_mode: Literal["direct", "proxy", "shadow", "replay"] | None = None
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    estimated_cost: float = 0.0


class ProxyRequest(BaseModel):
    project_id: str = "local"
    routing_decision_id: str | None = None
    capability_id: str
    provider_id: str
    tool_id: str
    estimated_cost: float = 0.0
    request: dict[str, Any]
