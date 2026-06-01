import hashlib
import json
from pathlib import Path

from scripts.api2agent_openapi_real_spec_calibration import (
    CalibrationCase,
    cached_metadata_for_case,
    classify_case_status,
    case_output_dir,
    default_manifest,
    run_calibration,
    write_synthetic_large_spec,
)


FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


def test_default_manifest_includes_required_calibration_slots(tmp_path: Path) -> None:
    write_synthetic_large_spec(tmp_path / "synthetic_large.openapi.json", operation_count=3)

    cases = default_manifest(root=Path("."), inputs_dir=tmp_path)
    purposes = {case.purpose for case in cases}

    assert {
        "small_reference",
        "large_rest",
        "auth_rich",
        "server_rich",
        "schema_rich",
        "write_heavy",
    } <= purposes
    assert any(case.optional for case in cases)
    assert any(case.case_id == "cached_petstore_expanded" and not case.optional for case in cases)


def test_case_output_dir_is_contained_and_sanitized(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"

    output = case_output_dir(generated_dir, "../Unsafe Case")

    assert generated_dir.resolve() in output.parents
    assert output.name == "unsafe_case"


def test_classify_case_status_pass_warn_fail_and_skipped() -> None:
    base = {
        "generated": True,
        "diagnostics_status": "pass",
        "diagnostics_score": 90,
        "inspect_excerpt": ["Tool count: 1"],
        "tool_count": 1,
        "read_tools": 1,
        "write_tools": 0,
        "delete_tools": 0,
        "readme_bytes": 100,
        "generation_ms": 10,
        "schema_hint_counts": {},
        "sample_tool_details": ["get: GET /items [read]"],
    }

    assert classify_case_status(base) == ("pass", [])

    warn_status, warn_reasons = classify_case_status({**base, "tool_count": 51})
    assert warn_status == "warn"
    assert "tool_count > 50" in warn_reasons

    fail_status, fail_reasons = classify_case_status({**base, "generated": False, "generation_error": "boom"})
    assert fail_status == "fail"
    assert fail_reasons == ["boom"]

    skipped_status, skipped_reasons = classify_case_status({"skipped": True, "skip_reason": "missing"})
    assert skipped_status == "skipped"
    assert skipped_reasons == ["missing"]


def test_run_calibration_writes_contract_and_skips_optional_case(tmp_path: Path) -> None:
    cases = [
        CalibrationCase(
            case_id="basic",
            purpose="small_reference",
            source_path=FIXTURES / "basic.yaml",
        ),
        CalibrationCase(
            case_id="missing_optional",
            purpose="large_rest",
            source_path=tmp_path / "missing.yaml",
            optional=True,
        ),
    ]

    report = run_calibration(cases=cases, out_dir=tmp_path / "calibration", root=Path("."))
    result_path = tmp_path / "calibration" / "result.json"

    assert result_path.exists()
    assert report["contract_version"] == "api2agent.openapi_real_spec_calibration.v0"
    assert report["summary"]["case_count"] == 2
    assert report["summary"]["generated_count"] == 1
    assert report["summary"]["skipped"] == 1
    assert report["cases"][0]["case_id"] == "basic"
    assert report["cases"][0]["generated"] is True
    assert report["cases"][0]["tool_count"] == 1
    assert report["cases"][0]["inspect_excerpt"]
    assert report["cases"][0]["sample_tool_details"]
    assert report["cases"][0]["inspect_line_count"] >= len(report["cases"][0]["inspect_excerpt"])
    assert report["cases"][0]["sample_tool_detail_line_count"] >= 1
    assert report["cases"][0]["max_inspect_line_chars"] >= 1
    assert report["cases"][0]["readme_tool_section_lines"] >= 1
    assert "repeated_finding_groups" in report["cases"][0]
    assert report["cases"][0]["first_call_params"]["params"]["user_id"] == "user_123"
    assert report["cases"][0]["generic_example_count"] == 0
    assert report["cases"][0]["generic_first_call_params"] == []
    assert report["cases"][1]["status"] == "skipped"


def test_cached_metadata_is_validated_and_emitted(tmp_path: Path) -> None:
    source = _write_cached_source(tmp_path)
    metadata = _write_cached_metadata(tmp_path, source)
    case = CalibrationCase(
        case_id="cached_basic",
        purpose="cached_real_small",
        source_path=source,
        metadata_path=metadata,
    )

    report = run_calibration(cases=[case], out_dir=tmp_path / "calibration", root=tmp_path)

    result = report["cases"][0]
    assert result["status"] == "pass"
    assert result["source_name"] == "Cached Basic Fixture"
    assert result["source_license"] == "Apache-2.0"
    assert result["cache_sha256"].startswith("sha256:")
    assert result["cache_policy"] == "test committed cache"


def test_cached_metadata_checksum_mismatch_fails_case(tmp_path: Path) -> None:
    source = _write_cached_source(tmp_path)
    metadata = _write_cached_metadata(tmp_path, source, sha256="sha256:bad")
    case = CalibrationCase(
        case_id="cached_basic",
        purpose="cached_real_small",
        source_path=source,
        metadata_path=metadata,
    )

    report = run_calibration(cases=[case], out_dir=tmp_path / "calibration", root=tmp_path)

    assert report["cases"][0]["status"] == "fail"
    assert report["cases"][0]["status_reasons"] == ["cached metadata sha256 does not match source file"]


def test_cached_metadata_missing_for_required_case_fails(tmp_path: Path) -> None:
    source = _write_cached_source(tmp_path)
    case = CalibrationCase(
        case_id="cached_basic",
        purpose="cached_real_small",
        source_path=source,
        metadata_path=source.with_suffix(".metadata.json"),
    )

    report = run_calibration(cases=[case], out_dir=tmp_path / "calibration", root=tmp_path)

    assert report["cases"][0]["status"] == "fail"
    assert "cached metadata_path does not exist" in report["cases"][0]["status_reasons"][0]


def test_cached_metadata_rejects_paths_outside_inputs(tmp_path: Path) -> None:
    source = tmp_path / "outside.yaml"
    source.write_text((FIXTURES / "basic.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    metadata = tmp_path / ".dogfood" / "openapi-real-spec-calibration" / "inputs" / "cached-real" / "outside.metadata.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text("{}", encoding="utf-8")
    case = CalibrationCase(
        case_id="outside",
        purpose="cached_real_small",
        source_path=source,
        metadata_path=metadata,
    )

    _, error = cached_metadata_for_case(case, root=tmp_path)

    assert error == f"cached source_path is outside calibration inputs: {source}"


def test_run_calibration_flags_synthetic_large_surface(tmp_path: Path) -> None:
    spec = tmp_path / "synthetic_large.openapi.json"
    write_synthetic_large_spec(spec, operation_count=51)
    cases = [
        CalibrationCase(
            case_id="large",
            purpose="large_rest",
            source_path=spec,
        )
    ]

    report = run_calibration(cases=cases, out_dir=tmp_path / "calibration", root=Path("."))

    assert report["cases"][0]["tool_count"] == 51
    assert report["cases"][0]["status"] == "warn"
    assert "tool_count > 50" in report["cases"][0]["status_reasons"]
    assert report["summary"]["largest_package_case"] == "large"


def _write_cached_source(tmp_path: Path) -> Path:
    source = tmp_path / ".dogfood" / "openapi-real-spec-calibration" / "inputs" / "cached-real" / "basic.openapi.yaml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text((FIXTURES / "basic.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return source


def _write_cached_metadata(tmp_path: Path, source: Path, *, sha256: str | None = None) -> Path:
    digest = sha256 or "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = source.with_suffix(".metadata.json")
    metadata.write_text(
        json.dumps(
            {
                "case_id": "cached_basic",
                "purpose": "cached_real_small",
                "source_name": "Cached Basic Fixture",
                "source_url": "https://example.com/basic.yaml",
                "source_license": "Apache-2.0",
                "source_retrieved_at": "2026-06-01",
                "cache_policy": "test committed cache",
                "reduction_policy": "none",
                "redaction_policy": "none needed",
                "sha256": digest,
                "notes": "test metadata",
            }
        ),
        encoding="utf-8",
    )
    return metadata
