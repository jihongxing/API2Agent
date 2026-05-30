# Go Data Plane Credential Config Dogfood Report

Date: 2026-05-30

## Goal

Verify that Go Data Plane can load a local project credential config and inject a provider credential without requiring each `/v1/execute` request to carry credential intent.

This is the local BYOK step before hosted credential vault work.

## Semantics

Credential config is:

- local JSON only in this slice
- loaded at Data Plane startup through `API2AGENT_CREDENTIAL_CONFIG`
- resolved before provider execution
- injected into headers, query params, or body patches
- recorded only as redacted metadata in `UsageEvent`

Resolution order:

```text
request credential intent -> config credential -> none
```

Config credential matching uses:

- `provider_id`
- exact `owner_id == project_id`
- fallback project owner `owner_id == local`
- first matching config credential

Scope and lifecycle checks still apply.

## Dogfood Command

```bash
python scripts/go_dataplane_credential_config_dogfood.py \
  --output .dogfood/go-dataplane-credential-config/report.json
```

The script builds:

- `api2agent-dataplane`
- `api2agent-conformance`

## Observed Result

The dogfood starts Go Data Plane with:

```bash
API2AGENT_CREDENTIAL_CONFIG=<temp>/credentials.json
API2AGENT_CONFIG_TOKEN=config-secret
```

The request does not include a `credential` object.

Observed behavior:

- provider was called once
- provider received `api_key=config-secret`
- response succeeded
- `UsageEvent.credential_reference` was `config:cred_config_ipify`
- `resolution_strategy` was `static`
- credential metadata source was `config`
- raw secret did not appear in emitted events
- Protocol v0.2 conformance passed

## Result

Go Data Plane Credential Config v0 passed.

The Go Data Plane can now use local config credentials as a stand-in for future project-owned vault credentials.

## Non-Goals

This slice does not add:

- hosted vault
- encrypted credential storage
- YAML config loading
- OAuth / delegated credentials
- UI credential management
