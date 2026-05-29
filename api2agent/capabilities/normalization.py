from typing import Any


class OutputNormalizationError(ValueError):
    pass


def normalize_output(body: Any, output_mapping: dict[str, str]) -> dict[str, Any]:
    if not output_mapping:
        return body if isinstance(body, dict) else {"value": body}

    normalized: dict[str, Any] = {}
    missing: list[str] = []
    for output_field, expression in output_mapping.items():
        found, value = _extract_json_path(body, expression)
        if not found:
            missing.append(f"{output_field} <- {expression}")
            continue
        normalized[output_field] = value

    if missing:
        raise OutputNormalizationError("Missing output mappings: " + ", ".join(missing))

    return normalized


def _extract_json_path(body: Any, expression: str) -> tuple[bool, Any]:
    if expression == "$":
        return True, body

    if not expression.startswith("$."):
        raise OutputNormalizationError(f"Unsupported output mapping expression: {expression}")

    current = body
    for part in expression[2:].split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return False, None
    return True, current
