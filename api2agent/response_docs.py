from __future__ import annotations

import json
from typing import Any, Mapping

from api2agent.schema_shaping import summarize_schema


NO_BODY_STATUS_CODES = {"204", "304"}
MAX_RESPONSE_SUMMARIES = 5
MAX_EXAMPLE_CHARS = 120


def response_category(status_code: object) -> str:
    status = str(status_code or "").strip().lower()
    if status == "default":
        return "default"
    if len(status) == 3 and status.isdigit():
        if status.startswith("2"):
            return "success"
        if status.startswith("3"):
            return "redirect"
        if status.startswith("4"):
            return "client_error"
        if status.startswith("5"):
            return "server_error"
    return "unknown"


def is_no_body_status(status_code: object) -> bool:
    return str(status_code or "").strip() in NO_BODY_STATUS_CODES


def response_has_example(response: object) -> bool:
    return _get(response, "example") is not None or bool(_get(response, "examples") or [])


def format_response_summary(
    response: object,
    *,
    include_description: bool = True,
    include_example: bool = True,
) -> str:
    status_code = str(_get(response, "status_code") or "unknown")
    category = response_category(status_code)
    content_type = _get(response, "content_type")
    schema = _get(response, "schema") or {}
    description = _get(response, "description")

    parts = [status_code, category]
    if content_type:
        parts.append(str(content_type))

    if schema:
        parts.append(summarize_schema(schema, direction="response"))
    elif is_no_body_status(status_code):
        parts.append("no documented body")
    elif content_type:
        parts.append("undocumented schema")
    else:
        parts.append("no documented body")

    summary = " ".join(parts)
    example = _format_response_example(response) if include_example else ""
    if example:
        summary += f" example={example}"
    if include_description and description:
        summary += f" - {description}"
    return summary


def format_response_summaries(responses: list[object], *, limit: int = MAX_RESPONSE_SUMMARIES) -> list[str]:
    summaries = [format_response_summary(response) for response in responses[:limit]]
    if len(responses) > limit:
        summaries.append(f"... {len(responses) - limit} more responses")
    return summaries


def response_category_counts(responses: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for response in responses:
        category = response_category(_get(response, "status_code"))
        counts[category] = counts.get(category, 0) + 1
    return counts


def _get(response: object, field: str) -> Any:
    if isinstance(response, Mapping):
        if field == "schema":
            return response.get("schema") or response.get("schema_")
        return response.get(field)
    if field == "schema":
        return getattr(response, "schema_", None)
    return getattr(response, field, None)


def _format_response_example(response: object) -> str:
    example = _get(response, "example")
    if example is None:
        examples = _get(response, "examples") or []
        if examples:
            example = examples[0]
    if example is None:
        return ""

    rendered = json.dumps(example, ensure_ascii=False, sort_keys=True)
    if len(rendered) > MAX_EXAMPLE_CHARS:
        rendered = rendered[: MAX_EXAMPLE_CHARS - 3] + "..."
    return rendered
