from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class CostEstimate(BaseModel):
    estimated_cost: float = 0.0
    observed_cost: float | None = None
    cost_source: Literal["estimated", "provider_declared", "observed", "contracted"] = "estimated"


class AdapterResult(BaseModel):
    ok: bool
    capability_id: str
    provider_id: str
    output: dict[str, Any] | None = None
    status_code: int | None = None
    latency_ms: float = 0.0
    cost: CostEstimate = Field(default_factory=CostEstimate)
    error_type: str | None = None
    error_message: str | None = None


class ProviderAdapter(Protocol):
    capability_id: str
    provider_id: str

    def call(self, input: dict[str, Any]) -> AdapterResult:
        ...

    def estimate_cost(self, input: dict[str, Any]) -> CostEstimate:
        ...
