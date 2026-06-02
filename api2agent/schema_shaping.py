from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Literal


SchemaDirection = Literal["neutral", "request", "response"]

LARGE_OBJECT_PROPERTY_THRESHOLD = 12
MAX_SCHEMA_BRANCHES = 3
MAX_OBJECT_FIELDS = 8
MAX_MARKER_VALUE_LENGTH = 48

STRING_CONSTRAINT_KEYWORDS = {"format", "pattern", "minLength", "maxLength"}
NUMERIC_CONSTRAINT_KEYWORDS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
ARRAY_CONSTRAINT_KEYWORDS = {"minItems", "maxItems", "uniqueItems"}
VISIBLE_SCHEMA_KEYWORDS = (
    "format",
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minItems",
    "maxItems",
    "uniqueItems",
    "const",
    "deprecated",
)
UNSUPPORTED_SCHEMA_KEYWORDS = (
    "multipleOf",
    "minProperties",
    "maxProperties",
    "patternProperties",
    "propertyNames",
    "dependentRequired",
    "dependentSchemas",
    "if",
    "then",
    "else",
    "not",
    "contains",
    "minContains",
    "maxContains",
    "unevaluatedProperties",
    "unevaluatedItems",
)
CONDITIONAL_SCHEMA_KEYWORDS = {"if", "then", "else", "not"}
DEPENDENT_SCHEMA_KEYWORDS = {"dependentRequired", "dependentSchemas"}


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


def discriminator_info(schema: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(schema, dict):
        return None
    raw_discriminator = schema.get("discriminator")
    if not isinstance(raw_discriminator, dict):
        return None

    property_name = raw_discriminator.get("propertyName")
    mapping = raw_discriminator.get("mapping")
    return {
        "property_name": str(property_name) if isinstance(property_name, str) and property_name.strip() else None,
        "mapping": {str(key): str(value) for key, value in mapping.items()} if isinstance(mapping, dict) else {},
        "has_polymorphism": _schema_has_polymorphism(schema),
        "unresolved_mappings": unresolved_discriminator_mappings(schema),
        "untagged_branches": discriminator_untagged_branches(schema),
    }


def select_discriminator_branch(schema: dict[str, Any]) -> tuple[dict[str, Any], str | None] | None:
    info = discriminator_info(schema)
    if info is None or not info["property_name"]:
        return None

    branches = _polymorphic_branches(schema)
    if not branches:
        return None

    mapping = info["mapping"]
    if mapping:
        selected_value, target = next(iter(mapping.items()))
        selected_label = _mapping_target_label(target)
        for branch in branches:
            if _branch_label(branch) == selected_label:
                return branch, selected_value
        return branches[0], selected_value

    branch = branches[0]
    return branch, _discriminator_value_for_branch(branch, info["property_name"])


def unresolved_discriminator_mappings(schema: dict[str, Any]) -> list[str]:
    raw_discriminator = schema.get("discriminator") if isinstance(schema, dict) else None
    if not isinstance(raw_discriminator, dict):
        return []
    mapping = raw_discriminator.get("mapping")
    if not isinstance(mapping, dict):
        return []

    branch_labels = {
        label
        for branch in _polymorphic_branches(schema)
        for label in [_branch_label(branch)]
        if label
    }
    if not branch_labels:
        return []

    unresolved: list[str] = []
    for key, raw_target in mapping.items():
        target = str(raw_target)
        if target.startswith("#/") and _mapping_target_label(target) not in branch_labels:
            unresolved.append(str(key))
    return unresolved


def discriminator_untagged_branches(schema: dict[str, Any]) -> list[int]:
    info = discriminator_info_without_branch_checks(schema)
    if info is None or not info["property_name"]:
        return []

    untagged: list[int] = []
    for index, branch in enumerate(_polymorphic_branches(schema)):
        properties = branch.get("properties") or {}
        tag_schema = properties.get(info["property_name"])
        if not isinstance(tag_schema, dict):
            untagged.append(index)
            continue
        if not _discriminator_value_for_branch(branch, info["property_name"]):
            untagged.append(index)
    return untagged


def discriminator_info_without_branch_checks(schema: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(schema, dict):
        return None
    raw_discriminator = schema.get("discriminator")
    if not isinstance(raw_discriminator, dict):
        return None
    property_name = raw_discriminator.get("propertyName")
    mapping = raw_discriminator.get("mapping")
    return {
        "property_name": str(property_name) if isinstance(property_name, str) and property_name.strip() else None,
        "mapping": {str(key): str(value) for key, value in mapping.items()} if isinstance(mapping, dict) else {},
        "has_polymorphism": _schema_has_polymorphism(schema),
    }


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
        if str(key).startswith("x-api2agent-"):
            continue
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
        return _summarize_branches("oneOf", schema, schema["oneOf"], direction=direction, depth=depth)
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        return _summarize_branches("anyOf", schema, schema["anyOf"], direction=direction, depth=depth)

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
    schema: dict[str, Any],
    branches: list[Any],
    *,
    direction: SchemaDirection,
    depth: int,
) -> str:
    parts = _discriminator_branch_summaries(schema, branches, direction=direction, depth=depth)
    if parts is None:
        parts = [
            summarize_schema(branch if isinstance(branch, dict) else {}, direction=direction, depth=depth + 1)
            for branch in branches[:MAX_SCHEMA_BRANCHES]
        ]
    if len(branches) > MAX_SCHEMA_BRANCHES:
        parts.append("...")
    return f"{label}[" + " | ".join(parts) + "]"


def _discriminator_branch_summaries(
    schema: dict[str, Any],
    branches: list[Any],
    *,
    direction: SchemaDirection,
    depth: int,
) -> list[str] | None:
    info = discriminator_info_without_branch_checks(schema)
    if info is None or not info["property_name"]:
        return None

    prefix = f"discriminator={info['property_name']}: "
    mapping = info["mapping"]
    if mapping:
        parts = [
            f"{key}=>{_mapping_target_label(target)}"
            for key, target in list(mapping.items())[:MAX_SCHEMA_BRANCHES]
        ]
        return [prefix + parts[0], *parts[1:]] if parts else [prefix.rstrip()]

    branch_parts = [
        summarize_schema(branch if isinstance(branch, dict) else {}, direction=direction, depth=depth + 1)
        for branch in branches[:MAX_SCHEMA_BRANCHES]
    ]
    return [prefix + branch_parts[0], *branch_parts[1:]] if branch_parts else [prefix.rstrip()]


def _schema_markers(schema: dict[str, Any], *, direction: SchemaDirection) -> list[str]:
    markers: list[str] = []
    if "format" in schema:
        markers.append(f"format={_marker_value(schema['format'])}")
    if "pattern" in schema:
        markers.append(f"pattern={_marker_value(schema['pattern'])}")
    if "minLength" in schema:
        markers.append(f"minLength={_marker_value(schema['minLength'])}")
    if "maxLength" in schema:
        markers.append(f"maxLength={_marker_value(schema['maxLength'])}")
    if "minimum" in schema:
        markers.append(f"min={_marker_value(schema['minimum'])}")
    if "maximum" in schema:
        markers.append(f"max={_marker_value(schema['maximum'])}")
    if "exclusiveMinimum" in schema:
        markers.append(f"exclusiveMin={_marker_value(schema['exclusiveMinimum'])}")
    if "exclusiveMaximum" in schema:
        markers.append(f"exclusiveMax={_marker_value(schema['exclusiveMaximum'])}")
    if "minItems" in schema:
        markers.append(f"minItems={_marker_value(schema['minItems'])}")
    if "maxItems" in schema:
        markers.append(f"maxItems={_marker_value(schema['maxItems'])}")
    if schema.get("uniqueItems") is True:
        markers.append("uniqueItems")
    if "const" in schema:
        markers.append(f"const={_marker_value(schema['const'])}")
    if schema.get("deprecated") is True:
        markers.append("deprecated")
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


def _marker_value(value: Any) -> str:
    text = str(value)
    text = " ".join(text.split())
    if len(text) > MAX_MARKER_VALUE_LENGTH:
        return text[: MAX_MARKER_VALUE_LENGTH - 3] + "..."
    return text


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
    if any(key in schema for key in VISIBLE_SCHEMA_KEYWORDS + UNSUPPORTED_SCHEMA_KEYWORDS):
        counter["schema_keywords"] += 1
    if any(key in schema for key in STRING_CONSTRAINT_KEYWORDS):
        counter["string_constraints"] += 1
    if any(key in schema for key in NUMERIC_CONSTRAINT_KEYWORDS):
        counter["numeric_constraints"] += 1
    if any(key in schema for key in ARRAY_CONSTRAINT_KEYWORDS):
        counter["array_constraints"] += 1
    if "const" in schema:
        counter["const_schema"] += 1
    if schema.get("deprecated") is True:
        counter["deprecated_schema_fields"] += 1
    if "pattern" in schema:
        counter["pattern_schema"] += 1
    if any(key in schema for key in UNSUPPORTED_SCHEMA_KEYWORDS):
        counter["unsupported_schema_keywords"] += 1
    if any(key in schema for key in CONDITIONAL_SCHEMA_KEYWORDS):
        counter["conditional_schema"] += 1
    if any(key in schema for key in DEPENDENT_SCHEMA_KEYWORDS):
        counter["dependent_schema"] += 1
    if "additionalProperties" in schema:
        counter["maps"] += 1
    info = discriminator_info_without_branch_checks(schema)
    if info is not None:
        counter["discriminators"] += 1
        if info["mapping"]:
            counter["discriminator_mappings"] += 1
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
    if hint == "schema_keywords":
        return any(key in schema for key in VISIBLE_SCHEMA_KEYWORDS + UNSUPPORTED_SCHEMA_KEYWORDS)
    if hint == "string_constraints":
        return any(key in schema for key in STRING_CONSTRAINT_KEYWORDS)
    if hint == "numeric_constraints":
        return any(key in schema for key in NUMERIC_CONSTRAINT_KEYWORDS)
    if hint == "array_constraints":
        return any(key in schema for key in ARRAY_CONSTRAINT_KEYWORDS)
    if hint == "const_schema":
        return "const" in schema
    if hint == "deprecated_schema_fields":
        return schema.get("deprecated") is True
    if hint == "pattern_schema":
        return "pattern" in schema
    if hint == "unsupported_schema_keywords":
        return any(key in schema for key in UNSUPPORTED_SCHEMA_KEYWORDS)
    if hint == "conditional_schema":
        return any(key in schema for key in CONDITIONAL_SCHEMA_KEYWORDS)
    if hint == "dependent_schema":
        return any(key in schema for key in DEPENDENT_SCHEMA_KEYWORDS)
    if hint == "maps":
        return "additionalProperties" in schema
    if hint == "discriminators":
        return discriminator_info_without_branch_checks(schema) is not None
    if hint == "discriminator_mappings":
        info = discriminator_info_without_branch_checks(schema)
        return bool(info and info["mapping"])
    if hint == "discriminator_missing_property":
        info = discriminator_info_without_branch_checks(schema)
        return bool(info and not info["property_name"])
    if hint == "discriminator_without_polymorphism":
        info = discriminator_info_without_branch_checks(schema)
        return bool(info and not info["has_polymorphism"])
    if hint == "discriminator_mapping_unresolved":
        return bool(unresolved_discriminator_mappings(schema))
    if hint == "discriminator_branch_without_tag":
        return bool(discriminator_untagged_branches(schema))
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


def _schema_has_polymorphism(schema: dict[str, Any]) -> bool:
    return isinstance(schema.get("oneOf"), list) or isinstance(schema.get("anyOf"), list)


def _polymorphic_branches(schema: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("oneOf", "anyOf"):
        branches = schema.get(key)
        if isinstance(branches, list):
            return [branch for branch in branches if isinstance(branch, dict)]
    return []


def _branch_label(branch: dict[str, Any]) -> str | None:
    for key in ("title", "x-schema-name", "name"):
        value = branch.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _mapping_target_label(target: str) -> str:
    tail = str(target).rstrip("/").split("/")[-1] if target else ""
    return tail or str(target)


def _discriminator_value_for_branch(branch: dict[str, Any], property_name: str) -> str | None:
    properties = branch.get("properties") or {}
    tag_schema = properties.get(property_name)
    if not isinstance(tag_schema, dict):
        return None
    for key in ("const", "default", "example"):
        if tag_schema.get(key) is not None:
            return str(tag_schema[key])
    enum_values = tag_schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return str(enum_values[0])
    return None
