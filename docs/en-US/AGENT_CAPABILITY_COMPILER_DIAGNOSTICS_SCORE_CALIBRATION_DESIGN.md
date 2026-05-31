# Agent Capability Compiler Diagnostics Score Calibration Design v0

Date: 2026-06-01

Status: complete

## Decision

The next Agent Capability Compiler implementation slice should be:

```text
Agent Capability Compiler Diagnostics Score Calibration Implementation v0
```

This slice should recalibrate diagnostics scoring so metadata-rich OpenAPI packages are not punished as harshly as genuinely risky or broken packages. It should preserve existing finding severities and diagnostic status semantics for compatibility, but compute `score` from explicit finding impact/actionability rules and expose a `score_breakdown` for review.

## Why This Slice Now

The OpenAPI real-spec calibration harness produced a useful signal:

```text
OpenAPI real-spec calibration: 1 pass, 5 warn, 0 fail, 1 skipped
- schema_rich_keywords: warn score=50
- auth_rich_security: warn score=0
- server_rich_choices: warn score=20
```

These packages are intentionally metadata-rich. Their warnings and info findings are useful, but many are expected review notes rather than severe risks. The current score formula is too blunt:

```text
penalty = errors * 35 + warnings * 10 + min(info * 2, 10)
score = 100 - penalty
```

That formula treats all warnings equally. It also allows many expected metadata findings to push packages into scores that look worse than their actual usability.

## Current Baseline

Already present:

- deterministic findings with `id`, `severity`, `category`, `message`, `location`, `recommendation`, and `evidence`
- summary counts by severity
- status derived from severity counts:
  - `fail` if any errors
  - `warn` if any warnings
  - `pass` otherwise
- score derived only from severity counts
- calibration harness captures diagnostics status, score, summary, and finding counts

Important gap:

- score does not distinguish user-actionable risks from expected metadata richness
- no score breakdown explains why a package lost points
- positive readiness findings, such as `proxy_identity_ready`, still contribute to info volume and can indirectly reduce score
- metadata visibility findings can dominate score for complex but valid OpenAPI specs

## Goals

- preserve existing diagnostics JSON compatibility
- keep existing `severity` and `status` semantics stable
- make `score` reflect user-actionable risk more than metadata volume
- add machine-readable score explanation
- reduce false-low scores for metadata-rich but usable packages
- keep true failures and unsafe packages visible
- make calibration harness output more useful for deciding next hardening tasks

## Non-Goals

Do not implement:

- new parser behavior
- new OpenAPI schema semantics
- runtime request or response validation
- LLM-based diagnostic triage
- provider execution
- hosted diagnostics service
- workflow runtime
- marketplace/provider onboarding
- vault, billing, public CRUD, gateway permission source, or automatic propagation

## Compatibility Strategy

Keep existing fields:

```text
contract_version
status
score
summary
metrics
generation_context
findings
```

Add optional fields:

```text
score_breakdown
scoring_profile
```

Existing consumers that only read `status`, `score`, `summary`, and `findings` remain compatible.

Keep `status` severity-based in v0. A package with warnings still reports `warn`, even if calibrated score is high.

## Scoring Model

Introduce a small score profile:

```text
api2agent.diagnostics.score_profile.v0
```

Each finding id should map to one impact class:

| Impact | Meaning | Suggested Penalty |
| --- | --- | --- |
| `blocking` | generation/runtime cannot be trusted | 35 |
| `action_required` | likely needs user action before Agent use | 10 |
| `review_required` | useful review item, not necessarily blocking | 4 |
| `metadata_review` | expected metadata visibility or caveat | 1 |
| `readiness` | positive readiness signal | 0 |

Score formula:

```text
penalty = sum(finding penalties)
score = max(0, min(100, 100 - penalty))
```

Cap `metadata_review` penalties:

```text
metadata_review_penalty <= 8
```

This keeps rich schemas from losing large score chunks just because the compiler is now more transparent.

## Initial Finding Impact Mapping

### Blocking

- `duplicate_tool_names`
- `missing_base_url`
- `required_body_without_schema`

### Action Required

- `large_toolset`
- `no_read_tools`
- `write_only_package`
- `generic_capability_name`
- `generic_tool_name`
- `unknown_safety`
- `write_tools_present`
- `weak_tool_description`
- `many_required_parameters`
- `array_without_item_schema`
- `discriminator_missing_property`
- `discriminator_without_polymorphism`
- `discriminator_mapping_unresolved`
- `success_response_without_schema`
- `unsupported_auth_scheme`
- `unknown_auth`
- `auth_env_missing`
- `relative_server_url`

### Review Required

- `broad_object_schema`
- `read_only_request_fields`
- `write_only_response_fields`
- `conditional_schema_present`
- `dependent_schema_present`
- `deprecated_schema_fields` when emitted as warning

### Metadata Review

- `missing_provider_region`
- `missing_parameter_descriptions`
- `additional_properties_present`
- `nullable_fields_present`
- `nested_polymorphic_schema`
- `large_object_schema`
- `schema_keywords_present`
- `string_constraints_present`
- `numeric_constraints_present`
- `array_constraints_present`
- `const_schema_present`
- `pattern_schema_present`
- `unsupported_schema_keywords_present`
- `discriminator_present`
- `discriminator_mapping_present`
- `discriminator_branch_without_tag`
- `response_schema_present`
- `response_example_present`
- `response_without_schema`
- `error_response_schema_present`
- `default_response_present`
- `multiple_response_content_types`
- `response_polymorphic_schema`
- `auth_alternatives_present`
- `combined_auth_required`
- `query_api_key_auth`
- `cookie_api_key_auth`
- `metadata_only_oauth`
- `multiple_servers_present`
- `ambiguous_server_profiles`
- `server_variables_present`
- `path_server_override`
- `operation_server_override`
- `mixed_auth_summary`

### Readiness

- `proxy_identity_ready`

Unknown finding ids should default to `review_required` if severity is warning/error and `metadata_review` if severity is info.

## Score Breakdown Shape

Add:

```json
{
  "scoring_profile": "api2agent.diagnostics.score_profile.v0",
  "score_breakdown": {
    "base": 100,
    "penalty": 18,
    "score": 82,
    "impact_counts": {
      "blocking": 0,
      "action_required": 1,
      "review_required": 0,
      "metadata_review": 4,
      "readiness": 1
    },
    "penalties": {
      "blocking": 0,
      "action_required": 10,
      "review_required": 0,
      "metadata_review": 8,
      "readiness": 0
    },
    "finding_impacts": {
      "large_toolset": "action_required",
      "schema_keywords_present": "metadata_review"
    }
  }
}
```

Keep this compact enough for generated `diagnostics.json`.

## Calibration Expectations

After implementation:

- `small_reference_basic` should remain high score
- `large_rest_synthetic` should still warn because `tool_count > 50`
- `write_heavy_unsafe` should still show meaningful penalty for no read/write-only behavior
- `auth_rich_security` should no longer score near zero solely because it preserves many auth metadata findings
- `server_rich_choices` should no longer score near zero solely because it exposes server metadata
- `schema_rich_keywords` should improve while still warning for conditional/dependent request-body caveats

Suggested target:

```text
metadata-rich expected cases should score >= 60 unless they also have blocking/action_required risks.
```

## Implementation Plan

1. Add score profile constants in `api2agent/diagnostics.py`.
2. Add a helper that maps each finding to impact and penalty.
3. Replace `_score(summary)` with score computation from findings.
4. Keep `_status(summary)` unchanged.
5. Add `score_breakdown` and `scoring_profile` to diagnostics output.
6. Update formatting only if needed to keep `diagnostics_summary_line` stable.
7. Add tests for old high-risk packages, metadata-rich packages, readiness findings, unknown finding fallback, and score breakdown shape.
8. Rerun the real-spec calibration harness and document before/after scores.

## Tests

Add or update tests for:

- duplicate tool names still produce low score/fail
- missing base URL still produces low score/fail
- write-only packages still warn with meaningful penalty
- metadata-rich security combinations score higher than the old blunt formula
- server-rich packages score higher than the old blunt formula
- schema keyword visibility findings are capped as metadata penalties
- `proxy_identity_ready` has zero penalty
- `score_breakdown` includes impact counts, penalties, and finding impact mapping
- diagnostics contract remains backward compatible for existing fields

## Dogfood

Run:

```text
python scripts\api2agent_openapi_real_spec_calibration.py
```

Compare before/after:

- `auth_rich_security`
- `server_rich_choices`
- `schema_rich_keywords`
- `write_heavy_unsafe`
- `large_rest_synthetic`

The implementation report should include the score delta.

## Success Metrics

The implementation is successful when:

- full Python test suite passes
- diagnostics remain backward compatible
- score breakdown explains penalties
- metadata-rich calibration cases no longer look catastrophically unhealthy solely because they preserve useful metadata
- true risk cases still warn/fail visibly
- calibration harness output is more useful for choosing next hardening work

## Acceptance Criteria For This Design

- current scoring weakness is documented
- compatibility strategy is defined
- impact classes and initial mapping are defined
- score formula and metadata cap are defined
- score breakdown shape is defined
- calibration expectations are defined
- implementation plan, tests, and dogfood are named
- non-goals preserve API-first compiler boundaries
