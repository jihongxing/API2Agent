from __future__ import annotations

from typing import Any

from api2agent.ir.models import Parameter, RequestBody


def example_for_parameter(parameter: Parameter) -> Any:
    value, ok = _first_present(
        parameter.example,
        _first_item(parameter.examples),
        parameter.schema_.get("default"),
        parameter.schema_.get("example"),
        _first_item(parameter.schema_.get("examples")),
        _first_item(parameter.schema_.get("enum")),
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
    return example_value(request_body.schema_, required_only=True)


def example_value(schema: dict, *, required_only: bool = False) -> Any:
    value, ok = _first_present(
        schema.get("default"),
        schema.get("example"),
        _first_item(schema.get("examples")),
        _first_item(schema.get("enum")),
    )
    if ok:
        return value

    schema_type = schema.get("type")
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
        return [example_value(schema.get("items") or {})]
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1
    if schema_type == "boolean":
        return True
    return "example"


def _first_present(*values: Any) -> tuple[Any, bool]:
    for value in values:
        if value is not None:
            return value, True
    return None, False


def _first_item(value: Any) -> Any | None:
    if isinstance(value, list) and value:
        return value[0]
    return None
