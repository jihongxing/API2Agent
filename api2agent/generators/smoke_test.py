from api2agent.ir.models import Capability, SafetyLevel


def render_smoke_test(capability: Capability) -> str:
    read_tool = next((tool for tool in capability.tools if tool.safety == SafetyLevel.READ), None)
    if read_tool is None:
        return '''"""Generated smoke test."""


def main() -> None:
    print("No read-only endpoint was detected. Add a manual test before calling write/delete tools.")


if __name__ == "__main__":
    main()
'''

    params = {
        parameter.name: _example_value(parameter.schema_)
        for parameter in read_tool.parameters
        if parameter.required
    }

    return f'''"""Generated smoke test."""

from runner import execute_tool


def main() -> None:
    result = execute_tool("{read_tool.name}", {params!r})
    print(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''


def _example_value(schema: dict) -> object:
    schema_type = schema.get("type")
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1
    if schema_type == "boolean":
        return True
    return "example"
