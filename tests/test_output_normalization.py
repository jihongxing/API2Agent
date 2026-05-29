import pytest

from api2agent.capabilities.models import ProviderCandidate
from api2agent.capabilities.normalization import OutputNormalizationError, normalize_output


def test_normalizes_ipify_public_ip_output() -> None:
    provider = ProviderCandidate(
        id="ipify_public_ip",
        capability_id="public_ip_lookup",
        provider_id="ipify",
        tool_id="get",
        output_mapping={"ip": "$.ip"},
    )

    result = normalize_output({"ip": "108.174.61.76"}, provider.output_mapping)

    assert result == {"ip": "108.174.61.76"}


def test_normalizes_httpbin_public_ip_output() -> None:
    provider = ProviderCandidate(
        id="httpbin_public_ip",
        capability_id="public_ip_lookup",
        provider_id="httpbin",
        tool_id="get_ip",
        output_mapping={"ip": "$.origin"},
    )

    result = normalize_output({"origin": "108.174.61.76"}, provider.output_mapping)

    assert result == {"ip": "108.174.61.76"}


def test_normalizes_nested_output_path() -> None:
    result = normalize_output(
        {"data": {"result": {"id": "item_123"}}},
        {"id": "$.data.result.id"},
    )

    assert result == {"id": "item_123"}


def test_normalization_reports_missing_fields() -> None:
    with pytest.raises(OutputNormalizationError) as exc:
        normalize_output({"origin": "108.174.61.76"}, {"ip": "$.ip"})

    assert "ip <- $.ip" in str(exc.value)


def test_normalization_without_mapping_passes_dict_through() -> None:
    assert normalize_output({"ok": True}, {}) == {"ok": True}
