from random import Random

from api2agent.capabilities.models import MetricsSnapshot, ProviderCandidate, RoutingPolicy


def select_provider(
    candidates: list[ProviderCandidate],
    metrics: list[MetricsSnapshot],
    policy: RoutingPolicy | None = None,
) -> ProviderCandidate | None:
    ranked = rank_providers(candidates, metrics, policy)
    return ranked[0] if ranked else None


def select_provider_region(candidate: ProviderCandidate, client_region: str | None = None) -> str | None:
    if client_region and client_region in candidate.regions:
        return client_region
    if "global" in candidate.regions:
        return "global"
    if candidate.geo_affinity == "global":
        return "global"
    if candidate.geo_affinity == "cn-only":
        return "cn"
    if candidate.regions:
        return candidate.regions[0]
    return None


def rank_providers(
    candidates: list[ProviderCandidate],
    metrics: list[MetricsSnapshot],
    policy: RoutingPolicy | None = None,
) -> list[ProviderCandidate]:
    if not candidates:
        return []

    policy = policy or RoutingPolicy()
    metrics_by_provider = {item.provider_id: item for item in metrics}

    if policy.strategy == "first":
        return candidates

    if policy.strategy == "random":
        shuffled = list(candidates)
        Random(0).shuffle(shuffled)
        return shuffled

    if policy.strategy == "lowest_cost":
        return sorted(candidates, key=lambda candidate: _cost(candidate, metrics_by_provider))

    if policy.strategy == "lowest_latency":
        return sorted(candidates, key=lambda candidate: _latency(candidate, metrics_by_provider))

    if policy.strategy == "region_aware_latency":
        return sorted(candidates, key=lambda candidate: _region_aware_latency(candidate, metrics, policy.client_region))

    if policy.strategy == "highest_success_rate":
        return sorted(
            candidates,
            key=lambda candidate: _success_rate(candidate, metrics_by_provider),
            reverse=True,
        )

    return sorted(
        candidates,
        key=lambda candidate: _balanced_score(candidate, candidates, metrics_by_provider, policy),
        reverse=True,
    )


def _success_rate(candidate: ProviderCandidate, metrics: dict[str, MetricsSnapshot]) -> float:
    snapshot = metrics.get(candidate.provider_id)
    return snapshot.success_rate if snapshot else 0.0


def _latency(candidate: ProviderCandidate, metrics: dict[str, MetricsSnapshot]) -> float:
    snapshot = metrics.get(candidate.provider_id)
    if snapshot and snapshot.total_calls:
        return snapshot.average_latency_ms
    return float("inf")


def _region_aware_latency(
    candidate: ProviderCandidate,
    metrics: list[MetricsSnapshot],
    client_region: str | None,
) -> tuple[int, float]:
    matching_metrics = [
        item
        for item in metrics
        if item.provider_id == candidate.provider_id
        and item.total_calls
        and (client_region is None or item.client_region == client_region)
    ]
    if matching_metrics:
        return (_region_rank(candidate, client_region), min(item.average_latency_ms for item in matching_metrics))

    provider_metrics = [item for item in metrics if item.provider_id == candidate.provider_id and item.total_calls]
    if provider_metrics:
        return (_region_rank(candidate, client_region), min(item.average_latency_ms for item in provider_metrics))

    return (_region_rank(candidate, client_region), float("inf"))


def _region_rank(candidate: ProviderCandidate, client_region: str | None) -> int:
    if not client_region:
        return 0
    if client_region in candidate.regions:
        return 0
    if candidate.geo_affinity == "global":
        return 1
    if candidate.geo_affinity == "unknown":
        return 2
    return 3


def _cost(candidate: ProviderCandidate, metrics: dict[str, MetricsSnapshot]) -> float:
    snapshot = metrics.get(candidate.provider_id)
    if snapshot and snapshot.total_calls:
        return snapshot.estimated_cost_per_call
    return candidate.estimated_cost


def _balanced_score(
    candidate: ProviderCandidate,
    candidates: list[ProviderCandidate],
    metrics: dict[str, MetricsSnapshot],
    policy: RoutingPolicy,
) -> float:
    success_weight = policy.weights.get("success_rate", 0.5)
    latency_weight = policy.weights.get("latency", 0.3)
    cost_weight = policy.weights.get("cost", 0.2)

    success = _success_rate(candidate, metrics)
    latency = _normalized_inverse(
        _latency(candidate, metrics),
        [_latency(item, metrics) for item in candidates],
    )
    cost = _normalized_inverse(
        _cost(candidate, metrics),
        [_cost(item, metrics) for item in candidates],
    )

    return success * success_weight + latency * latency_weight + cost * cost_weight


def _normalized_inverse(value: float, values: list[float]) -> float:
    finite_values = [item for item in values if item != float("inf")]
    if value == float("inf") or not finite_values:
        return 0.0

    minimum = min(finite_values)
    maximum = max(finite_values)
    if minimum == maximum:
        return 1.0

    return 1.0 - ((value - minimum) / (maximum - minimum))
