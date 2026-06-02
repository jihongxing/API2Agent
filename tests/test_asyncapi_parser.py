from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.asyncapi import count_asyncapi_http_operations_file, parse_asyncapi, parse_asyncapi_file


FIXTURES = Path(__file__).parent / "fixtures" / "asyncapi"


def test_parse_asyncapi_http_webhook_to_capability() -> None:
    capability = parse_asyncapi_file(FIXTURES / "basic_webhook.yaml")

    assert capability.name == "order_events_api"
    assert capability.version == "1.0.0"
    assert capability.base_url == "https://hooks.example.com"
    assert capability.source.endswith("basic_webhook.yaml")
    assert capability.auth.type == "bearer"
    assert capability.auth.env == "ORDER_EVENTS_API_TOKEN"
    assert [tool.name for tool in capability.tools] == ["send_order_created"]

    tool = capability.tools[0]
    assert tool.operation_id == "sendOrderCreated"
    assert tool.method == "POST"
    assert tool.path == "/webhooks/order-created"
    assert tool.tags == ["asyncapi", "publish"]
    assert tool.safety == SafetyLevel.WRITE
    assert tool.request_body is not None
    assert tool.request_body.content_type == "application/json"
    assert tool.request_body.schema_["properties"]["order_id"]["type"] == "string"
    assert tool.request_body.schema_["properties"]["amount"]["type"] == "number"
    assert tool.request_body.example == {"order_id": "ord_123", "amount": 42.5, "expedited": False}
    assert tool.responses[0].status_code == "202"


def test_count_asyncapi_http_operations_file_skips_non_http_channels() -> None:
    assert count_asyncapi_http_operations_file(FIXTURES / "basic_webhook.yaml") == 1


def test_asyncapi_requires_callable_http_operation() -> None:
    with pytest.raises(ValueError, match="callable HTTP"):
        parse_asyncapi({"asyncapi": "3.0.0", "info": {"title": "bad"}, "channels": {}})
