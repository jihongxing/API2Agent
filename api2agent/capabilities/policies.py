from api2agent.capabilities.models import RoutingPolicy


def routing_policy_preset(name: str) -> RoutingPolicy:
    normalized = name.strip().lower().replace("-", "_")
    if normalized == "balanced":
        return RoutingPolicy(
            strategy="balanced",
            weights={"success_rate": 0.5, "latency": 0.3, "cost": 0.2},
        )
    if normalized == "reliability_first":
        return RoutingPolicy(
            strategy="balanced",
            weights={"success_rate": 0.8, "latency": 0.1, "cost": 0.1},
        )
    if normalized == "cost_first":
        return RoutingPolicy(
            strategy="balanced",
            weights={"success_rate": 0.1, "latency": 0.2, "cost": 0.7},
        )
    if normalized == "latency_first":
        return RoutingPolicy(
            strategy="balanced",
            weights={"success_rate": 0.1, "latency": 0.7, "cost": 0.2},
        )

    raise ValueError(f"Unknown routing policy preset: {name}")
