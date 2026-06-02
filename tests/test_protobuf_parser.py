from pathlib import Path

import pytest

from api2agent.ir.models import SafetyLevel
from api2agent.parsers.protobuf import count_proto_unary_rpcs_file, parse_proto, parse_proto_file


FIXTURES = Path(__file__).parent / "fixtures" / "protobuf"


def test_parse_proto_unary_rpc_to_grpc_scaffold() -> None:
    capability = parse_proto_file(FIXTURES / "user_service.proto")

    assert capability.name == "demo_users_v1"
    assert capability.base_url == "grpc://localhost:50051"
    assert capability.source.endswith("user_service.proto")
    assert capability.auth.type == "none"
    assert [tool.name for tool in capability.tools] == ["user_service_get_user"]

    tool = capability.tools[0]
    assert tool.operation_id == "demo.users.v1.UserService.GetUser"
    assert tool.method == "POST"
    assert tool.path == "/demo.users.v1.UserService/GetUser"
    assert tool.tags == ["grpc", "UserService"]
    assert tool.safety == SafetyLevel.UNKNOWN
    assert tool.request_body is not None
    assert tool.request_body.schema_["properties"]["user_id"]["type"] == "string"
    assert tool.request_body.schema_["properties"]["include_profile"]["type"] == "boolean"
    assert tool.request_body.schema_["x-api2agent-grpc"] == {
        "package": "demo.users.v1",
        "service": "UserService",
        "method": "GetUser",
        "requestType": "GetUserRequest",
        "responseType": "User",
    }
    assert tool.responses[0].schema_["properties"]["tags"]["items"]["type"] == "string"


def test_count_proto_unary_rpcs_file_skips_streaming() -> None:
    assert count_proto_unary_rpcs_file(FIXTURES / "user_service.proto") == 1


def test_proto_requires_service() -> None:
    with pytest.raises(ValueError, match="service"):
        parse_proto('syntax = "proto3"; message Empty {}')
