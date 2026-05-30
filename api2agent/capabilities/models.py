from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CapabilityDefinition(BaseModel):
    id: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    safety: Literal["read", "write", "delete", "unknown"] = "unknown"


class ProviderCandidate(BaseModel):
    id: str
    capability_id: str
    provider_id: str
    tool_id: str
    estimated_cost: float = 0.0
    regions: list[str] = Field(default_factory=list)
    geo_affinity: Literal["global", "regional", "cn-only", "unknown"] = "unknown"
    output_mapping: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricsSnapshot(BaseModel):
    capability_id: str
    provider_id: str
    client_region: str | None = None
    provider_region: str | None = None
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    average_latency_ms: float = 0.0
    estimated_cost_per_call: float = 0.0


class DecisionDatasetRecord(BaseModel):
    request_id: str
    routing_decision_id: str | None = None
    project_id: str = "local"
    capability_id: str
    client_region: str | None = None
    api2agent_region: str | None = None
    candidate_provider_ids: list[str] = Field(default_factory=list)
    selected_provider_id: str | None = None
    routing_strategy: str
    success: bool = False
    latency_total_ms: float | None = None
    estimated_cost: float = 0.0
    error_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoutingPolicy(BaseModel):
    strategy: Literal[
        "first",
        "random",
        "lowest_cost",
        "lowest_latency",
        "region_aware_latency",
        "highest_success_rate",
        "balanced",
    ] = "balanced"
    client_region: str | None = None
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "success_rate": 0.5,
            "latency": 0.3,
            "cost": 0.2,
        }
    )


class FailoverPolicy(BaseModel):
    enabled: bool = False
    max_attempts: int = 1
    retry_on_error_types: list[str] = Field(
        default_factory=lambda: [
            "http_error",
            "http_status",
            "proxy_error",
            "output_normalization",
        ]
    )
    retry_on_status_codes: list[int] = Field(default_factory=lambda: [408, 429, 500, 502, 503, 504])


class RoutingDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = "local"
    capability_id: str
    strategy: str
    preset: str | None = None
    client_region: str | None = None
    selected_provider_id: str | None = None
    ranked_provider_ids: list[str] = Field(default_factory=list)
    metrics: list[MetricsSnapshot] = Field(default_factory=list)
    failover_policy: FailoverPolicy | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
