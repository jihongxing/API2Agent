from pathlib import Path

from scripts.api2agent_openapi_real_spec_calibration import (
    CalibrationCase,
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
    assert report["cases"][1]["status"] == "skipped"


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
