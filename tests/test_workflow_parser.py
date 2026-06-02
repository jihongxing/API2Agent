from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.workflow import parse_workflow_file, parse_workflow_manifest


FIXTURES = Path(__file__).parent / "fixtures" / "workflow"


def test_parse_workflow_manifest_to_one_tool_capability() -> None:
    capability = parse_workflow_file(FIXTURES / "basic_manifest.json")

    assert capability.name == "invoice_approval_workflow"
    assert capability.version == "1.0.0"
    assert capability.base_url == "https://hooks.example.com"
    assert capability.source.endswith("basic_manifest.json")
    assert capability.auth.type == "api_key"
    assert capability.auth.env == "INVOICE_WORKFLOW_KEY"
    assert capability.auth.header == "X-Workflow-Key"
    assert len(capability.tools) == 1

    tool = capability.tools[0]
    params = {parameter.name: parameter for parameter in tool.parameters}
    assert tool.name == "trigger_invoice_approval"
    assert tool.method == "POST"
    assert tool.path == "/workflows/invoice-approval"
    assert tool.tags == ["workflow"]
    assert tool.safety == SafetyLevel.WRITE
    assert params["source"].location == "query"
    assert params["source"].schema_["default"] == "agent"
    assert tool.request_body is not None
    assert tool.request_body.schema_["properties"]["invoice_id"]["type"] == "string"
    assert tool.request_body.example["invoice_id"] == "inv_123"
    assert tool.responses[0].schema_["properties"]["workflow_run_id"]["type"] == "string"


def test_workflow_manifest_requires_http_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint.url"):
        parse_workflow_manifest({"name": "bad", "endpoint": {"url": "ftp://example.com/hook"}})
