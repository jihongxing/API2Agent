from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Literal


SchemaDirection = Literal["neutral", "request", "response"]

LARGE_OBJECT_PROPERTY_THRESHOLD = 12
MAX_SCHEMA_BRANCHES = 3
MAX_OBJECT_FIELDS = 8


def shape_schema(schema: dict[str, Any], *, direction: SchemaDirection = "neutral") -> dict[str, Any]:
    """Return a direction-aware schema copy without mutating the raw OpenAPI schema."""
    shaped = _shape_value(schema, direction=direction)
    return shaped if isinstance(shaped, dict) else {}


def summarize_schema(schema: dict[str, Any], *, direction: SchemaDirection = "neutral", depth: int = 0) -> str:
    if not isinstance(schema, dict) or not schema:
        return "unknown"

    schema = shape_schema(schema, direction=direction)
    base = _summarize_schema(schema, direction=direction, depth=depth)
    markers = _schema_markers(schema, direction=direction)
    if markers:
        base += " " + " ".join(markers)
    return base


def schema_hint_counts(schema: dict[str, Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    _collect_schema_hints(schema if isinstance(schema, dict) else {}, counter, depth=0)
    return dict(counter)


def merge_schema_hint_counts(*counts: dict[str, int]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in counts:
        counter.update(item)
    return dict(counter)


def schema_paths_with_hint(schema: dict[str, Any], hint: str) -> list[str]:
    paths: list[str] = []
    _collect_paths(schema if isinstance(schema, dict) else {}, hint, "$", paths, depth=0)
    return paths


def is_nullable_schema(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type") if isinstance(schema, dict) else None
    return bool(
        isinstance(schema, dict)
        and (
            schema.get("nullable") is True
            or (isinstance(schema_type, list) and "null" in schema_type)
        )
    )


def _shape_value(value: Any, *, direction: SchemaDirection) -> Any:
    if isinstance(value, list):
        return [_shape_value(item, direction=direction) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)

    shaped: dict[str, Any] = {}
    for key, raw_item in value.items():
        if key == "properties" and isinstance(raw_item, dict):
            properties: dict[str, Any] = {}
            skipped: set[str] = set()
            for name, raw_property in raw_item.items():
                if not isinstance(raw_property, dict):
                    properties[str(name)] = _shape_value(raw_property, direction=direction)
                    continue
                if direction == "request" and raw_property.get("readOnly") is True:
                    skipped.add(str(name))
                    continue
                if direction == "response" and raw_property.get("writeOnly") is True:
                    skipped.add(str(name))
                    continue
                properties[str(name)] = _shape_value(raw_property, direction=direction)
            shaped[key] = properties
            if skipped and isinstance(value.get("required"), list):
                shaped["required"] = [item for item in value["required"] if str(item) not in skipped]
            continue
        if key == "required" and key in shaped:
            continue
        shaped[key] = _shape_value(raw_item, direction=direction)
    return shaped


def _summarize_schema(schema: dict[str, Any], *, direction: SchemaDirection, depth: int) -> str:
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        return _summarize_branches("oneOf", schema["oneOf"], direction=direction, depth=depth)
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        return _summarize_branches("anyOf", schema["anyOf"], direction=direction, depth=depth)

    schema_type = _primary_type(schema)
    if schema_type == "object":
        return _summarize_object(schema, direction=direction, depth=depth)
    if schema_type == "array":
        items = schema.get("items")
        item_summary = summarize_schema(items, direction=direction, depth=depth + 1) if isinstance(items, dict) else "unknown"
        return f"array[{item_summary}]"

    label = str(schema_type or "unknown")
    if "default" in schema:
        label += f" default={schema['default']}"
    return label


def _summarize_object(schema: dict[str, Any], *, direction: SchemaDirection, depth: int) -> str:
    properties = schema.get("properties") or {}
    additional = schema.get("additionalProperties")
    required = {str(item) for item in schema.get("required") or []}

    if not properties:
        if isinstance(additional, dict):
            return f"object map[{summarize_schema(additional, direction=direction, depth=depth + 1)}]"
        if additional is True:
            return "object map[unknown]"
        return "object"

    field_labels = []
    for index, (name, raw_property) in enumerate(properties.items()):
        if index >= MAX_OBJECT_FIELDS:
            field_labels.append("...")
            break
        child = raw_property if isinstance(raw_property, dict) else {}
        suffix = "" if str(name) in required else "?"
        field_labels.append(f"{name}:{summarize_schema(child, direction=direction, depth=depth + 1)}{suffix}")

    if isinstance(additional, dict):
        field_labels.append(f"*:{summarize_schema(additional, direction=direction, depth=depth + 1)}")
    elif additional is True:
        field_labels.append("*:unknown")

    return "object {" + ", ".join(field_labels) + "}"


def _summarize_branches(
    label: str,
    branches: list[Any],
    *,
    direction: SchemaDirection,
    depth: int,
) -> str:
    parts = [
        summarize_schema(branch if isinstance(branch, dict) else {}, direction=direction, depth=depth + 1)
        for branch in branches[:MAX_SCHEMA_BRANCHES]
    ]
    if len(branches) > MAX_SCHEMA_BRANCHES:
        parts.append("...")
    return f"{label}[" + " | ".join(parts) + "]"


def _schema_markers(schema: dict[str, Any], *, direction: SchemaDirection) -> list[str]:
    markers: list[str] = []
    if is_nullable_schema(schema):
        markers.append("nullable")
    if direction == "neutral":
        if schema.get("readOnly") is True:
            markers.append("readOnly")
        if schema.get("writeOnly") is True:
            markers.append("writeOnly")
    elif direction == "request" and schema.get("writeOnly") is True:
        markers.append("writeOnly")
    elif direction == "response" and schema.get("readOnly") is True:
        markers.append("readOnly")
    return markers


def _primary_type(schema: dict[str, Any]) -> str | None:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [str(item) for item in schema_type if item != "null"]
        return non_null[0] if non_null else "null"
    if schema_type is not None:
        return str(schema_type)
    if "properties" in schema or "additionalProperties" in schema:
        return "object"
    return None


def _collect_schema_hints(schema: dict[str, Any], counter: Counter[str], *, depth: int) -> None:
    if not isinstance(schema, dict):
        return

    if is_nullable_schema(schema):
        counter["nullable"] += 1
    if schema.get("readOnly") is True:
        counter["read_only"] += 1
    if schema.get("writeOnly") is True:
        counter["write_only"] += 1
    if "additionalProperties" in schema:
        counter["maps"] += 1
    if any(key in schema for key in ("oneOf", "anyOf")):
        counter["polymorphic"] += 1
        if depth > 0:
            counter["nested_polymorphic"] += 1
    if _primary_type(schema) == "array" and "items" not in schema:
        counter["arrays_without_items"] += 1
    properties = schema.get("properties") or {}
    if isinstance(properties, dict) and len(properties) > LARGE_OBJECT_PROPERTY_THRESHOLD:
        counter["large_objects"] += 1

    for child in _schema_children(schema):
        _collect_schema_hints(child, counter, depth=depth + 1)


def _collect_paths(schema: dict[str, Any], hint: str, path: str, paths: list[str], *, depth: int) -> None:
    if not isinstance(schema, dict):
        return

    if _schema_has_hint(schema, hint, depth=depth):
        paths.append(path)

    properties = schema.get("properties") or {}
    if isinstance(properties, dict):
        for name, child in properties.items():
            if isinstance(child, dict):
                _collect_paths(child, hint, f"{path}.properties.{name}", paths, depth=depth + 1)
    items = schema.get("items")
    if isinstance(items, dict):
        _collect_paths(items, hint, f"{path}.items", paths, depth=depth + 1)
    for key in ("oneOf", "anyOf", "allOf"):
        branches = schema.get(key)
        if isinstance(branches, list):
            for index, child in enumerate(branches):
                if isinstance(child, dict):
                    _collect_paths(child, hint, f"{path}.{key}[{index}]", paths, depth=depth + 1)
    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        _collect_paths(additional, hint, f"{path}.additionalProperties", paths, depth=depth + 1)


def _schema_has_hint(schema: dict[str, Any], hint: str, *, depth: int) -> bool:
    if hint == "nullable":
        return is_nullable_schema(schema)
    if hint == "read_only":
        return schema.get("readOnly") is True
    if hint == "write_only":
        return schema.get("writeOnly") is True
    if hint == "maps":
        return "additionalProperties" in schema
    if hint == "nested_polymorphic":
        return depth > 0 and any(key in schema for key in ("oneOf", "anyOf"))
    if hint == "arrays_without_items":
        return _primary_type(schema) == "array" and "items" not in schema
    if hint == "large_objects":
        properties = schema.get("properties") or {}
        return isinstance(properties, dict) and len(properties) > LARGE_OBJECT_PROPERTY_THRESHOLD
    return False


def _schema_children(schema: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    properties = schema.get("properties") or {}
    if isinstance(properties, dict):
        children.extend(child for child in properties.values() if isinstance(child, dict))

    items = schema.get("items")
    if isinstance(items, dict):
        children.append(items)

    for key in ("oneOf", "anyOf", "allOf"):
        branches = schema.get(key)
        if isinstance(branches, list):
            children.extend(child for child in branches if isinstance(child, dict))

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        children.append(additional)

    return children
