# Provider Registry Contract

## Scope

This document defines the stable local provider registry fields used by:

- `api2agent route`
- `api2agent call`

It does not define hosted registry APIs, provider onboarding APIs, marketplace APIs, payment APIs, or revenue share mechanics.

## Contract Version

Current contract version:

- `provider_registry.v0.1`

If `contract_version` is omitted, API2Agent treats the registry as `provider_registry.v0.1` for local compatibility.

Unsupported contract versions must fail before routing.

## Registry Shape

```json
{
  "contract_version": "provider_registry.v0.1",
  "providers": []
}
```

## Stable Provider Fields

The following provider fields are stable:

- `id`
- `capability_id`
- `provider_id`
- `tool_id`
- `estimated_cost`
- `output_mapping`
- `metadata`

## Stable Metadata Fields

The following `metadata` field is stable for local execution:

- `package_dir`

Additional metadata fields may be added later.

## Example

```json
{
  "contract_version": "provider_registry.v0.1",
  "providers": [
    {
      "id": "ipify_public_ip",
      "capability_id": "public_ip_lookup",
      "provider_id": "ipify",
      "tool_id": "get",
      "estimated_cost": 0.001,
      "output_mapping": {
        "ip": "$.ip"
      },
      "metadata": {
        "package_dir": ".dogfood/ipify"
      }
    }
  ]
}
```

## Compatibility Rule

API2Agent may add optional fields later, but must not remove or rename the stable fields above without a documented contract version change.

## Inspection

Inspect a registry locally:

```bash
api2agent registry capability-registry.json --json
```

Stable inspection fields:

- `contract_version`
- `provider_count`
- `capability_counts`
- `warnings`
- `providers`

Warnings are advisory for `api2agent registry`.

For `api2agent call`, missing local package directories or missing `runner.py` files for the requested capability fail before execution.

Warning shape:

```json
{
  "severity": "error",
  "code": "missing_runner",
  "provider_id": "ipify",
  "message": "runner not found at .dogfood/ipify/runner.py"
}
```

Severity levels:

- `info`: useful context that does not affect execution
- `warning`: suspicious metadata that does not block execution
- `error`: invalid local execution metadata that blocks `api2agent call`

`api2agent route --json` and `api2agent call --json` include:

- `registry_contract_version`
