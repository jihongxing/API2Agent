# API2Agent Generated Package Region Metadata Report v0

Date: 2026-05-31

Status: complete

## Summary

Generated packages can now carry optional provider-region intent without changing routing behavior.

This is a metadata-only Tooling Layer change:

- API-first only
- no workflow engine
- no routing rewrite
- no marketplace or billing work
- no credential vault work

## What Changed

### CLI Metadata Input

`api2agent generate` now accepts:

```bash
api2agent generate \
  --curl "curl https://api.example.com/items" \
  --name example_items \
  --provider-region us-east
```

Generated `capability.json` includes:

```json
{
  "provider_region": "us-east",
  "provider_regions": ["us-east"]
}
```

### Generated README Guidance

Generated package README files now include a Provider Region section.

When region metadata is configured, the README shows the generated provider-region intent and documents runtime override through:

```bash
API2AGENT_PROVIDER_REGION=us-east
```

### Proxy Payload Propagation

Generated runners now include `provider_region` in proxy payloads:

```json
{
  "provider_id": "example_items",
  "provider_region": "us-east"
}
```

`API2AGENT_PROVIDER_REGION` overrides generated metadata at runtime. This allows local or regional dogfoods to supply a region without regenerating packages.

## Dogfood

Repro command:

```bash
python scripts/api2agent_generated_region_metadata_dogfood.py
```

Artifact:

```text
.dogfood/generated-region-metadata/result.json
```

Dogfood checks:

- `capability.provider_region == "us-east"`
- `capability.provider_regions == ["us-east"]`
- generated runner proxy payload includes `provider_region == "us-east"`
- scope remains API-first

## Tests

Added regression coverage for:

- CLI writes provider-region metadata into generated `capability.json`
- generated runner proxy payload includes provider region
- `API2AGENT_PROVIDER_REGION` runtime override wins over generated metadata
- generated README documents provider-region intent

Validated:

```text
python scripts/api2agent_generated_region_metadata_dogfood.py
python scripts/api2agent_tooling_baseline_audit.py
python -m pytest tests/test_cli.py tests/test_runner_generation.py tests/test_generators.py
```

## Remaining Gap

The next Tooling Re-entry gap is authenticated proxy dogfood coverage.

The baseline audit verified no-auth proxy paths and direct bearer execution, but it intentionally did not run bearer calls through proxy credential config. The next task should close that observable-path gap without introducing a credential vault.

Next task:

```text
Proxy-mode Credential Dogfood Expansion v0
```

