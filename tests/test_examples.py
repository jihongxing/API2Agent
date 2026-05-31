from api2agent.generators.examples import example_for_parameter, example_value
from api2agent.ir.models import Parameter


def test_example_for_parameter_uses_name_aware_string_fallback() -> None:
    parameter = Parameter(name="user_id", location="path", required=True, schema={"type": "string"})

    assert example_for_parameter(parameter) == "user_123"


def test_example_for_parameter_preserves_format_over_name_hint() -> None:
    parameter = Parameter(
        name="user_id",
        location="path",
        required=True,
        schema={"type": "string", "format": "uuid"},
    )

    assert example_for_parameter(parameter) == "00000000-0000-4000-8000-000000000000"


def test_example_value_threads_object_property_names() -> None:
    schema = {
        "type": "object",
        "required": ["name", "password", "limit", "active"],
        "properties": {
            "name": {"type": "string"},
            "password": {"type": "string"},
            "limit": {"type": "integer"},
            "active": {"type": "boolean"},
        },
    }

    assert example_value(schema, required_only=True) == {
        "name": "Demo",
        "password": "REPLACE_ME",
        "limit": 10,
        "active": True,
    }


def test_example_value_applies_length_bounds_after_name_hint() -> None:
    assert example_value({"type": "string", "minLength": 6}, name="name") == "Demoxx"
