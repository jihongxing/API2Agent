from typing import Any

from api2agent.capabilities.models import FailoverPolicy


def should_failover(result: dict[str, Any], policy: FailoverPolicy) -> bool:
    if not policy.enabled:
        return False

    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    error_type = error.get("type")
    status_code = result.get("status_code")

    if error_type == "http_status" and status_code is not None:
        return int(status_code) in policy.retry_on_status_codes

    if error_type:
        return str(error_type) in policy.retry_on_error_types

    return False


def build_failover_policy(
    *,
    enabled: bool,
    candidate_count: int,
    max_attempts: int | None = None,
    retry_on_status_codes: list[int] | None = None,
) -> FailoverPolicy:
    attempts = max_attempts if max_attempts is not None else (candidate_count if enabled else 1)
    attempts = max(1, min(attempts, max(candidate_count, 1)))
    policy = FailoverPolicy(enabled=enabled, max_attempts=attempts)
    if retry_on_status_codes:
        policy.retry_on_status_codes = retry_on_status_codes
    return policy
