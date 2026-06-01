from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api2agent.cli import SCHEMA_HINT_PRIORITY, _format_counts, _format_tool_details, _tool_summary
from api2agent.filters import ToolFilter
from api2agent.generators.examples import example_for_parameter, example_for_request_body
from api2agent.generators.package import generate_package
from api2agent.ir.models import Capability, SafetyLevel
from api2agent.parsers.openapi import parse_openapi_file
from api2agent.response_docs import response_category_counts
from api2agent.schema_shaping import merge_schema_hint_counts, schema_hint_counts


CONTRACT_VERSION = "api2agent.openapi_real_spec_calibration.v0"
OUT_DIR = ROOT / ".dogfood" / "openapi-real-spec-calibration"
GENERATED_DIR = OUT_DIR / "generated"
INPUTS_DIR = OUT_DIR / "inputs"
RESULT_PATH = OUT_DIR / "result.json"


@dataclass(frozen=True)
class CalibrationFilters:
    include_tags: list[str] = field(default_factory=list)
    include_paths: list[str] = field(default_factory=list)
    include_operations: list[str] = field(default_factory=list)
    max_tools: int | None = None

    def to_tool_filter(self) -> ToolFilter:
        return ToolFilter(
            include_tags=self.include_tags,
            include_paths=self.include_paths,
            include_operations=self.include_operations,
            max_tools=self.max_tools,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "include_tags": self.include_tags,
            "include_paths": self.include_paths,
            "include_operations": self.include_operations,
            "max_tools": self.max_tools,
        }


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    purpose: str
    source_path: Path
    metadata_path: Path | None = None
    filters: CalibrationFilters = field(default_factory=CalibrationFilters)
    expected_status: str = "pass"
    optional: bool = False
    notes: str = ""


def main() -> None:
    report = run_calibration()
    print(_summary_table(report))
    print(f"Wrote {RESULT_PATH}")
    if report["summary"]["fail"] > 0:
        raise SystemExit(1)


def run_calibration(
    *,
    cases: list[CalibrationCase] | None = None,
    out_dir: Path = OUT_DIR,
    root: Path = ROOT,
) -> dict[str, Any]:
    out_dir = out_dir.resolve()
    generated_dir = out_dir / "generated"
    inputs_dir = out_dir / "inputs"
    result_path = out_dir / "result.json"
    _reset_directory(generated_dir, within=out_dir)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    if cases is None:
        write_synthetic_large_spec(inputs_dir / "synthetic_large.openapi.json", operation_count=60)
        cases = default_manifest(root=root, inputs_dir=inputs_dir)

    case_results = [
        run_case(case, generated_dir=generated_dir, root=root)
        for case in cases
    ]
    report = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": _utc_now(),
        "cases": case_results,
        "summary": build_summary(case_results),
        "recommendations": build_recommendations(case_results),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def default_manifest(*, root: Path = ROOT, inputs_dir: Path = INPUTS_DIR) -> list[CalibrationCase]:
    fixtures = root / "tests" / "fixtures" / "openapi"
    return [
        CalibrationCase(
            case_id="small_reference_basic",
            purpose="small_reference",
            source_path=fixtures / "basic.yaml",
            expected_status="pass",
            notes="Compact baseline package.",
        ),
        CalibrationCase(
            case_id="schema_rich_keywords",
            purpose="schema_rich",
            source_path=fixtures / "schema_keywords.yaml",
            expected_status="warn",
            notes="Keyword-rich schema fixture with conditional/dependent diagnostics.",
        ),
        CalibrationCase(
            case_id="auth_rich_security",
            purpose="auth_rich",
            source_path=fixtures / "security_combinations.yaml",
            expected_status="warn",
            notes="Security alternatives and combined auth metadata.",
        ),
        CalibrationCase(
            case_id="server_rich_choices",
            purpose="server_rich",
            source_path=fixtures / "server_choices.yaml",
            expected_status="warn",
            notes="Document, path, and operation server metadata.",
        ),
        CalibrationCase(
            case_id="write_heavy_unsafe",
            purpose="write_heavy",
            source_path=fixtures / "unsafe.yaml",
            expected_status="warn",
            notes="Write/delete-only package for manual path calibration.",
        ),
        CalibrationCase(
            case_id="large_rest_synthetic",
            purpose="large_rest",
            source_path=inputs_dir / "synthetic_large.openapi.json",
            expected_status="warn",
            notes="Local synthetic large-surface spec; no network dependency.",
        ),
        CalibrationCase(
            case_id="cached_petstore_expanded",
            purpose="cached_real_small",
            source_path=inputs_dir / "cached-real" / "petstore_expanded.openapi.json",
            metadata_path=inputs_dir / "cached-real" / "petstore_expanded.metadata.json",
            expected_status="pass",
            notes="Committed Apache-2.0 Swagger Petstore excerpt from the OpenAPI examples.",
        ),
        CalibrationCase(
            case_id="optional_cached_real_spec",
            purpose="large_rest",
            source_path=root / ".dogfood" / "openapi-real-spec-calibration" / "inputs" / "cached_real.openapi.json",
            expected_status="warn",
            optional=True,
            notes="Optional user-provided cached real spec.",
        ),
    ]


def run_case(case: CalibrationCase, *, generated_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    if not case.source_path.exists():
        if case.optional:
            return _skipped_case(case, "optional source_path is not present")
        return _failed_case(case, f"source_path does not exist: {case.source_path}")
    metadata, metadata_error = cached_metadata_for_case(case, root=root)
    if metadata_error is not None:
        return _failed_case(case, metadata_error)

    package_dir = case_output_dir(generated_dir, case.case_id)
    started = time.perf_counter()
    generation_error: str | None = None
    capability: Capability | None = None
    capability_json: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}
    inspect_excerpt: list[str] = []
    sample_tool_details: list[str] = []
    first_call_params: dict[str, Any] = {}

    try:
        if package_dir.exists():
            _reset_directory(package_dir, within=generated_dir)
        capability = parse_openapi_file(
            case.source_path,
            name=case.case_id,
            filters=case.filters.to_tool_filter(),
        )
        generate_package(capability, package_dir, force=True)
        capability_json = _read_json(package_dir / "capability.json")
        diagnostics = _read_json(package_dir / "diagnostics.json")
        inspect_excerpt, sample_tool_details = inspect_summary(capability_json)
        first_call_params = first_call_params_for(capability)
    except Exception as exc:
        generation_error = f"{type(exc).__name__}: {exc}"

    generation_ms = _elapsed_ms(started)
    metrics = case_metrics(
        case=case,
        package_dir=package_dir,
        capability_json=capability_json,
        diagnostics=diagnostics,
        cached_metadata=metadata,
        generation_ms=generation_ms,
        generation_error=generation_error,
        inspect_excerpt=inspect_excerpt,
        sample_tool_details=sample_tool_details,
        first_call_params=first_call_params,
    )
    status, reasons = classify_case_status(metrics)
    metrics["status"] = status
    metrics["status_reasons"] = reasons
    metrics["expected_status"] = case.expected_status
    return metrics


def case_metrics(
    *,
    case: CalibrationCase,
    package_dir: Path,
    capability_json: dict[str, Any],
    diagnostics: dict[str, Any],
    cached_metadata: dict[str, Any],
    generation_ms: float,
    generation_error: str | None,
    inspect_excerpt: list[str],
    sample_tool_details: list[str],
    first_call_params: dict[str, Any],
) -> dict[str, Any]:
    tools = capability_json.get("tools") or []
    safety_counts = _safety_counts(tools)
    required_parameter_count = sum(
        len([parameter for parameter in tool.get("parameters") or [] if parameter.get("required")])
        + (1 if (tool.get("request_body") or {}).get("required") else 0)
        for tool in tools
    )
    schema_hint_counts = _capability_schema_hint_counts(tools)
    response_counts = merge_response_category_counts(tools)
    finding_counts = _finding_counts(diagnostics.get("findings") or [])
    inspect_lines = [*inspect_excerpt, *sample_tool_details]
    generic_first_call_params = _generic_examples(first_call_params.get("params") or {})
    return {
        "case_id": case.case_id,
        "purpose": case.purpose,
        "source_path": str(case.source_path),
        "metadata_path": str(case.metadata_path) if case.metadata_path else None,
        "filters": case.filters.as_dict(),
        "optional": case.optional,
        "notes": case.notes,
        **cached_metadata,
        "package_dir": str(package_dir),
        "generated": generation_error is None,
        "generation_error": generation_error,
        "tool_count": len(tools),
        "read_tools": safety_counts["read"],
        "write_tools": safety_counts["write"],
        "delete_tools": safety_counts["delete"],
        "unknown_safety_tools": safety_counts["unknown"],
        "required_parameter_count": required_parameter_count,
        "schema_hint_counts": schema_hint_counts,
        "response_category_counts": response_counts,
        "diagnostics_status": diagnostics.get("status"),
        "diagnostics_score": diagnostics.get("score"),
        "diagnostics_summary": diagnostics.get("summary") or {},
        "finding_counts": finding_counts,
        "repeated_finding_groups": sum(1 for count in finding_counts.values() if count > 1),
        "readme_bytes": _file_size(package_dir / "README.md"),
        "readme_tool_section_lines": _readme_tool_section_lines(package_dir / "README.md"),
        "capability_bytes": _file_size(package_dir / "capability.json"),
        "generation_ms": generation_ms,
        "inspect_line_count": len(inspect_lines),
        "sample_tool_detail_line_count": len(sample_tool_details),
        "max_inspect_line_chars": max((len(line) for line in inspect_lines), default=0),
        "inspect_excerpt": inspect_excerpt[:5],
        "sample_tool_details": sample_tool_details[:5],
        "first_call_params": first_call_params,
        "generic_example_count": len(generic_first_call_params),
        "generic_first_call_params": generic_first_call_params,
    }


def classify_case_status(metrics: dict[str, Any]) -> tuple[str, list[str]]:
    if metrics.get("skipped"):
        return "skipped", [metrics.get("skip_reason") or "skipped"]
    if not metrics.get("generated"):
        return "fail", [metrics.get("generation_error") or "generation failed"]
    if metrics.get("diagnostics_status") is None:
        return "fail", ["diagnostics JSON is missing or unreadable"]
    if not metrics.get("inspect_excerpt"):
        return "fail", ["inspect excerpt could not be rendered"]

    reasons: list[str] = []
    if metrics.get("tool_count", 0) > 50:
        reasons.append("tool_count > 50")
    if metrics.get("diagnostics_status") == "fail":
        reasons.append("diagnostics_status == fail")
    score = metrics.get("diagnostics_score")
    if isinstance(score, int | float) and score < 60:
        reasons.append("diagnostics_score < 60")
    if metrics.get("readme_bytes", 0) > 200_000:
        reasons.append("readme_bytes > 200000")
    if metrics.get("generation_ms", 0) > 30_000:
        reasons.append("generation_ms > 30000")
    if metrics.get("read_tools", 0) == 0 and (metrics.get("write_tools", 0) or metrics.get("delete_tools", 0)):
        reasons.append("no read tools when write/delete tools exist")
    if metrics.get("schema_hint_counts") and not metrics.get("sample_tool_details"):
        reasons.append("schema hints present but no readable inspect detail")
    source_license = str(metrics.get("source_license") or "").lower()
    if "review_required" in source_license:
        reasons.append("source license metadata review required")
    return ("warn", reasons) if reasons else ("pass", [])


def build_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = {status: sum(1 for case in cases if case.get("status") == status) for status in ["pass", "warn", "fail", "skipped"]}
    generated_cases = [case for case in cases if case.get("generated")]
    largest = max(generated_cases, key=lambda item: item.get("tool_count", 0), default=None)
    noisiest = max(
        generated_cases,
        key=lambda item: sum((item.get("diagnostics_summary") or {}).values()),
        default=None,
    )
    return {
        **statuses,
        "case_count": len(cases),
        "generated_count": len(generated_cases),
        "largest_package_case": largest.get("case_id") if largest else None,
        "largest_package_tools": largest.get("tool_count") if largest else None,
        "noisiest_diagnostics_case": noisiest.get("case_id") if noisiest else None,
        "noisiest_diagnostics_findings": sum((noisiest.get("diagnostics_summary") or {}).values()) if noisiest else None,
    }


def build_recommendations(cases: list[dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    warn_cases = [case["case_id"] for case in cases if case.get("status") == "warn"]
    fail_cases = [case["case_id"] for case in cases if case.get("status") == "fail"]
    large_cases = [case["case_id"] for case in cases if case.get("tool_count", 0) > 50]
    low_score_cases = [case["case_id"] for case in cases if isinstance(case.get("diagnostics_score"), int | float) and case["diagnostics_score"] < 60]
    long_line_cases = [case["case_id"] for case in cases if case.get("max_inspect_line_chars", 0) > 180]
    repeated_finding_cases = [case["case_id"] for case in cases if case.get("repeated_finding_groups", 0) > 3]
    generic_example_cases = [case["case_id"] for case in cases if case.get("generic_example_count", 0) > 0]
    cached_warning_cases = [
        case["case_id"]
        for case in cases
        if case.get("metadata_path") and case.get("status") == "warn"
    ]
    if large_cases:
        recommendations.append("Review filter guidance and inspect truncation for large packages: " + ", ".join(large_cases))
    if low_score_cases:
        recommendations.append("Review diagnostics precision for low-score packages: " + ", ".join(low_score_cases))
    if long_line_cases:
        recommendations.append("Review summary line density for long inspect lines: " + ", ".join(long_line_cases))
    if repeated_finding_cases:
        recommendations.append("Review repeated diagnostics grouping for noisy packages: " + ", ".join(repeated_finding_cases))
    if generic_example_cases:
        recommendations.append("Review generic first-call params: " + ", ".join(generic_example_cases))
    if cached_warning_cases:
        recommendations.append("Review cached real-spec warnings: " + ", ".join(cached_warning_cases))
    if fail_cases:
        recommendations.append("Fix failed calibration cases before expanding the corpus: " + ", ".join(fail_cases))
    if warn_cases and not recommendations:
        recommendations.append("Review warning cases for summary readability and generated example quality: " + ", ".join(warn_cases))
    if not recommendations:
        recommendations.append("Calibration corpus is clean; add a cached real large spec before selecting the next hardening target.")
    return recommendations


def inspect_summary(capability_json: dict[str, Any]) -> tuple[list[str], list[str]]:
    tools = capability_json.get("tools") or []
    summary = _tool_summary(tools)
    lines = [
        f"Capability: {capability_json.get('name', 'unknown')}",
        f"Tool count: {len(tools)}",
        "Safety: " + ", ".join(f"{key}={value}" for key, value in summary["safety_counts"].items()),
    ]
    if summary["schema_hints"]:
        lines.append("Schema hints: " + _format_counts(summary["schema_hints"], priority=SCHEMA_HINT_PRIORITY))
    if summary["response_categories"]:
        lines.append("Response categories: " + _format_counts(summary["response_categories"]))

    sample_tool = next((tool for tool in tools if tool.get("safety") == "read"), None) or (tools[0] if tools else None)
    details: list[str] = []
    if sample_tool is not None:
        details.append(
            f"{sample_tool.get('name')}: {sample_tool.get('method')} {sample_tool.get('path')} [{sample_tool.get('safety')}]"
        )
        details.extend(_format_tool_details(sample_tool))
    return lines, details


def first_call_params_for(capability: Capability) -> dict[str, Any]:
    tool = next((item for item in capability.tools if item.safety == SafetyLevel.READ), None)
    if tool is None:
        tool = capability.tools[0] if capability.tools else None
    if tool is None:
        return {}
    params = {
        parameter.name: example_for_parameter(parameter)
        for parameter in tool.parameters
        if parameter.required or parameter.example is not None or parameter.examples
    }
    if tool.request_body is not None and tool.request_body.required:
        params["body"] = example_for_request_body(tool.request_body)
    return {"tool": tool.name, "params": params}


def merge_response_category_counts(tools: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tool in tools:
        for key, value in response_category_counts(tool.get("responses") or []).items():
            counts[key] = counts.get(key, 0) + value
    return dict(sorted(counts.items()))


def write_synthetic_large_spec(path: Path, *, operation_count: int = 60) -> None:
    paths: dict[str, Any] = {}
    for index in range(operation_count):
        paths[f"/items/{index}"] = {
            "get": {
                "operationId": f"getSyntheticItem{index}",
                "tags": ["synthetic"],
                "summary": f"Get synthetic item {index}.",
                "parameters": [
                    {
                        "name": "trace",
                        "in": "query",
                        "schema": {"type": "string", "default": "calibration"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string", "format": "uuid"},
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "Synthetic Large Calibration API", "version": "1.0.0"},
                "servers": [{"url": "https://api.example.com"}],
                "paths": paths,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


REQUIRED_CACHED_METADATA_FIELDS = {
    "case_id",
    "purpose",
    "source_name",
    "source_url",
    "source_license",
    "source_retrieved_at",
    "cache_policy",
    "reduction_policy",
    "redaction_policy",
    "sha256",
    "notes",
}


def cached_metadata_for_case(case: CalibrationCase, *, root: Path = ROOT) -> tuple[dict[str, Any], str | None]:
    if case.metadata_path is None:
        return {}, None
    inputs_root = (root / ".dogfood" / "openapi-real-spec-calibration" / "inputs").resolve()
    source_path = case.source_path.resolve()
    metadata_path = case.metadata_path.resolve()
    if inputs_root not in [source_path, *source_path.parents]:
        return {}, f"cached source_path is outside calibration inputs: {case.source_path}"
    if inputs_root not in [metadata_path, *metadata_path.parents]:
        return {}, f"cached metadata_path is outside calibration inputs: {case.metadata_path}"
    if not case.metadata_path.exists():
        return {}, f"cached metadata_path does not exist: {case.metadata_path}"
    try:
        metadata = _read_json(case.metadata_path)
    except Exception as exc:
        return {}, f"cached metadata_path is invalid JSON: {type(exc).__name__}: {exc}"
    missing = sorted(field for field in REQUIRED_CACHED_METADATA_FIELDS if not metadata.get(field))
    if missing:
        return {}, "cached metadata missing required fields: " + ", ".join(missing)
    if metadata.get("case_id") != case.case_id:
        return {}, "cached metadata case_id does not match calibration case"
    digest = "sha256:" + hashlib.sha256(case.source_path.read_bytes()).hexdigest()
    if metadata.get("sha256") != digest:
        return {}, "cached metadata sha256 does not match source file"
    return {
        "source_name": metadata["source_name"],
        "source_url": metadata["source_url"],
        "source_license": metadata["source_license"],
        "source_retrieved_at": metadata["source_retrieved_at"],
        "cache_sha256": metadata["sha256"],
        "cache_policy": metadata["cache_policy"],
        "reduction_policy": metadata["reduction_policy"],
        "redaction_policy": metadata["redaction_policy"],
    }, None


def case_output_dir(generated_dir: Path, case_id: str) -> Path:
    slug = _safe_slug(case_id)
    output = (generated_dir / slug).resolve()
    generated_root = generated_dir.resolve()
    if generated_root not in [output, *output.parents]:
        raise ValueError(f"Refusing output outside generated dir: {output}")
    return output


def _capability_schema_hint_counts(tools: list[dict[str, Any]]) -> dict[str, int]:
    counts: list[dict[str, int]] = []
    for tool in tools:
        for parameter in tool.get("parameters") or []:
            counts.append(schema_hint_counts(parameter.get("schema") or {}))
        request_body = tool.get("request_body") or {}
        if request_body:
            counts.append(schema_hint_counts(request_body.get("schema") or {}))
        for response in tool.get("responses") or []:
            counts.append(schema_hint_counts(response.get("schema") or {}))
    return dict(sorted(merge_schema_hint_counts(*counts).items()))


def _safety_counts(tools: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"read": 0, "write": 0, "delete": 0, "unknown": 0}
    for tool in tools:
        safety = str(tool.get("safety") or "unknown")
        counts[safety if safety in counts else "unknown"] += 1
    return counts


def _finding_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        finding_id = str(finding.get("id") or "unknown")
        counts[finding_id] = counts.get(finding_id, 0) + 1
    return dict(sorted(counts.items()))


def _skipped_case(case: CalibrationCase, reason: str) -> dict[str, Any]:
    metrics = {
        "case_id": case.case_id,
        "purpose": case.purpose,
        "source_path": str(case.source_path),
        "metadata_path": str(case.metadata_path) if case.metadata_path else None,
        "filters": case.filters.as_dict(),
        "optional": case.optional,
        "notes": case.notes,
        "generated": False,
        "skipped": True,
        "skip_reason": reason,
        "tool_count": 0,
        "read_tools": 0,
        "write_tools": 0,
        "delete_tools": 0,
        "unknown_safety_tools": 0,
        "required_parameter_count": 0,
        "schema_hint_counts": {},
        "response_category_counts": {},
        "diagnostics_status": None,
        "diagnostics_score": None,
        "diagnostics_summary": {},
        "finding_counts": {},
        "repeated_finding_groups": 0,
        "readme_bytes": 0,
        "readme_tool_section_lines": 0,
        "capability_bytes": 0,
        "generation_ms": 0,
        "inspect_line_count": 0,
        "sample_tool_detail_line_count": 0,
        "max_inspect_line_chars": 0,
        "inspect_excerpt": [],
        "sample_tool_details": [],
        "first_call_params": {},
        "generic_example_count": 0,
        "generic_first_call_params": [],
    }
    status, reasons = classify_case_status(metrics)
    metrics["status"] = status
    metrics["status_reasons"] = reasons
    metrics["expected_status"] = case.expected_status
    return metrics


def _failed_case(case: CalibrationCase, reason: str) -> dict[str, Any]:
    metrics = _skipped_case(case, reason)
    metrics.pop("skipped", None)
    metrics["skip_reason"] = None
    metrics["generation_error"] = reason
    metrics["status"] = "fail"
    metrics["status_reasons"] = [reason]
    return metrics


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _generic_examples(value: Any, *, path: str = "") -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            matches.extend(_generic_examples(child, path=child_path))
        return matches
    if isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_generic_examples(child, path=f"{path}[{index}]"))
        return matches
    if isinstance(value, str) and _is_generic_example(value):
        matches.append({"path": path or "$", "value": value})
    return matches


def _is_generic_example(value: str) -> bool:
    if value == "example":
        return True
    if value.startswith("example") and set(value[len("example"):]) <= {"x"}:
        return True
    return False


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _readme_tool_section_lines(path: Path) -> int:
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("## Tools") + 1
    except ValueError:
        return 0
    end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ") and index > start), len(lines))
    return max(0, end - start)


def _reset_directory(path: Path, *, within: Path) -> None:
    path = path.resolve()
    within = within.resolve()
    if within not in [path, *path.parents]:
        raise ValueError(f"Refusing to reset outside {within}: {path}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _safe_slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    return slug or "case"


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _summary_table(report: dict[str, Any]) -> str:
    lines = [
        f"OpenAPI real-spec calibration: {report['summary']['pass']} pass, "
        f"{report['summary']['warn']} warn, {report['summary']['fail']} fail, "
        f"{report['summary']['skipped']} skipped"
    ]
    for case in report["cases"]:
        reason = "; ".join(case.get("status_reasons") or [])
        suffix = f" - {reason}" if reason else ""
        lines.append(
            f"- {case['case_id']}: {case['status']} tools={case.get('tool_count', 0)} "
            f"score={case.get('diagnostics_score')}{suffix}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
