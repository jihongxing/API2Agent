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


def render_manual_write_test(capability: Capability) -> str:
    write_tool = next(
        (tool for tool in capability.tools if tool.safety in {SafetyLevel.WRITE, SafetyLevel.DELETE}),
        None,
    )
    if write_tool is None:
        return '''"""Generated manual write test."""


def main() -> None:
    print("No write/delete endpoint was detected.")


if __name__ == "__main__":
    main()
'''

    params = {
        parameter.name: _example_value(parameter.schema_)
        for parameter in write_tool.parameters
        if parameter.required
    }
    if write_tool.request_body is not None and write_tool.request_body.required:
        params["body"] = _example_value(write_tool.request_body.schema_)

    return f'''"""Generated manual write test.

This script can call a write/delete endpoint. It is disabled by default.
Run through `api2agent test --allow-write` or set API2AGENT_ALLOW_WRITE_TEST=1.
"""

import os

from runner import execute_tool


def main() -> None:
    if os.getenv("API2AGENT_ALLOW_WRITE_TEST") != "1":
        print("Manual write test is disabled. Run `api2agent test --allow-write` or set API2AGENT_ALLOW_WRITE_TEST=1.")
        raise SystemExit(2)

    result = execute_tool("{write_tool.name}", {params!r})
    print(result)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''


def _example_value(schema: dict) -> object:
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties") or {}
        return {
            name: _example_value(value)
            for name, value in properties.items()
        } or {}
    if schema_type == "array":
        return [_example_value(schema.get("items") or {})]
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1
    if schema_type == "boolean":
        return True
    return "example"
