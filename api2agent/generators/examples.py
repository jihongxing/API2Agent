from __future__ import annotations

from typing import Any

from api2agent.ir.models import Parameter, RequestBody
from api2agent.schema_shaping import select_discriminator_branch, shape_schema


def example_for_parameter(parameter: Parameter) -> Any:
    value, ok = _first_present(
        parameter.example,
        _first_item(parameter.examples),
        parameter.schema_.get("default"),
        parameter.schema_.get("example"),
        _first_item(parameter.schema_.get("examples")),
        _first_item(parameter.schema_.get("enum")),
        parameter.schema_.get("const"),
    )
    if ok:
        return value
    return example_value(parameter.schema_)


def example_for_request_body(request_body: RequestBody) -> Any:
    value, ok = _first_present(
        request_body.example,
        _first_item(request_body.examples),
        request_body.schema_.get("default"),
        request_body.schema_.get("example"),
        _first_item(request_body.schema_.get("examples")),
    )
    if ok:
        return value
    return example_value(shape_schema(request_body.schema_, direction="request"), required_only=True)


def example_value(schema: dict, *, required_only: bool = False) -> Any:
    value, ok = _first_present(
        schema.get("default"),
        schema.get("example"),
        _first_item(schema.get("examples")),
        _first_item(schema.get("enum")),
        schema.get("const"),
    )
    if ok:
        return value

    discriminator_selection = select_discriminator_branch(schema)
    if discriminator_selection is not None:
        branch, discriminator_value = discriminator_selection
        example = example_value(branch, required_only=required_only)
        if isinstance(example, dict):
            property_name = (schema.get("discriminator") or {}).get("propertyName")
            if isinstance(property_name, str) and property_name and discriminator_value is not None:
                example[property_name] = discriminator_value
        return example

    schema_type = _primary_type(schema)
    if schema_type == "object":
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        selected = {
            name: value
            for name, raw_schema in properties.items()
            if not required_only or not required or name in required
            for value in [example_value(raw_schema if isinstance(raw_schema, dict) else {})]
        }
        return selected or {}
    if schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            return []
        count = _array_example_count(schema)
        return [example_value(items) for _ in range(count)]
    if schema_type == "integer":
        return _numeric_example(schema, integer=True)
    if schema_type == "number":
        return _numeric_example(schema, integer=False)
    if schema_type == "boolean":
        return True
    return _string_example(schema)


def _primary_type(schema: dict) -> str | None:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        return str(non_null[0]) if non_null else "null"
    return str(schema_type) if schema_type is not None else None


def _first_present(*values: Any) -> tuple[Any, bool]:
    for value in values:
        if value is not None:
            return value, True
    return None, False


def _first_item(value: Any) -> Any | None:
    if isinstance(value, list) and value:
        return value[0]
    return None


def _string_example(schema: dict) -> str:
    format_examples = {
        "email": "user@example.com",
        "uri": "https://example.com",
        "url": "https://example.com",
        "uuid": "00000000-0000-4000-8000-000000000000",
        "date": "2026-01-01",
        "date-time": "2026-01-01T00:00:00Z",
        "hostname": "example.com",
    }
    value = format_examples.get(str(schema.get("format") or "").lower(), "example")

    min_length = _non_negative_int(schema.get("minLength"))
    max_length = _non_negative_int(schema.get("maxLength"))
    if min_length is not None and min_length <= 64 and len(value) < min_length:
        value += "x" * (min_length - len(value))
    if max_length is not None and len(value) > max_length:
        value = value[:max_length]
    return value


def _numeric_example(schema: dict, *, integer: bool) -> int | float:
    candidate: int | float = 1
    minimum = _number(schema.get("minimum"))
    maximum = _number(schema.get("maximum"))
    exclusive_minimum = _number(schema.get("exclusiveMinimum"))
    exclusive_maximum = _number(schema.get("exclusiveMaximum"))

    lower = exclusive_minimum if exclusive_minimum is not None else minimum
    upper = exclusive_maximum if exclusive_maximum is not None else maximum

    if lower is not None and candidate <= lower:
        candidate = lower + (1 if integer else 0.1)
    if upper is not None and candidate >= upper:
        candidate = upper - (1 if integer else 0.1)
    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum

    if integer:
        return int(candidate)
    return float(candidate) if isinstance(candidate, float) else candidate


def _array_example_count(schema: dict) -> int:
    min_items = _non_negative_int(schema.get("minItems"))
    max_items = _non_negative_int(schema.get("maxItems"))
    count = min_items if min_items is not None else 1
    count = max(1, min(count, 3))
    if max_items is not None:
        count = min(count, max_items)
    return max(0, count)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None
