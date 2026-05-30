from api2agent.capabilities.models import (
    CapabilityDefinition,
    MetricsSnapshot,
    FailoverPolicy,
    ProviderCandidate,
    RoutingDecision,
    RoutingPolicy,
)
from api2agent.capabilities.normalization import OutputNormalizationError, normalize_output
from api2agent.capabilities.policies import routing_policy_preset
from api2agent.capabilities.routing import rank_providers, select_provider, select_provider_region


def __getattr__(name: str):
    if name == "execute_capability":
        from api2agent.capabilities.execution import execute_capability

        return execute_capability
    raise AttributeError(name)

__all__ = [
    "CapabilityDefinition",
    "MetricsSnapshot",
    "FailoverPolicy",
    "ProviderCandidate",
    "RoutingDecision",
    "RoutingPolicy",
    "OutputNormalizationError",
    "normalize_output",
    "execute_capability",
    "routing_policy_preset",
    "rank_providers",
    "select_provider",
    "select_provider_region",
]
