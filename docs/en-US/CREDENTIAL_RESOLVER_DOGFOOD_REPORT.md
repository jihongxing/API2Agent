# Credential Resolver Dogfood Report

Date: May 30, 2026

## Goal

Verify that Credential Schema v0.1 and the local resolver can:

- resolve an env credential
- inject it into a generated provider package
- record only a redacted `credential_reference`
- keep raw secrets out of usage metadata
- replay the call when the credential can still be resolved

## Method

A local authenticated provider package was created under `.dogfood/credential-resolver/secure`.

The generated-style runner expects an injected `Authorization` header:

```text
Authorization: Bearer dogfood-secret
```

The secret was supplied through env:

```powershell
$env:DOGFOOD_API_TOKEN='dogfood-secret'
```

Command:

```bash
python -m api2agent.cli call .dogfood/credential-resolver/registry.json \
  --capability-id secure.data.get \
  --db .dogfood/credential-resolver/usage.sqlite \
  --strategy first \
  --json
```

Replay command:

```bash
python -m api2agent.cli replay d25e4ca5-7903-45f6-add3-128902889b81 \
  --db .dogfood/credential-resolver/usage.sqlite \
  --execute \
  --json
```

## Result

Call result:

- `ok`: `true`
- provider: `secure`
- normalized output: `{ "authorized": true }`
- credential reference: `env:DOGFOOD_API_TOKEN`

Usage event:

```json
{
  "credential_reference": "env:DOGFOOD_API_TOKEN",
  "request_metadata": {
    "credential": {
      "credential_id": "secure_DOGFOOD_API_TOKEN",
      "owner_type": "project",
      "owner_id": "local",
      "provider_id": "secure",
      "auth_type": "bearer",
      "injection_mode": "header",
      "injection_name": "Authorization",
      "source": "env",
      "secret_ref": "DOGFOOD_API_TOKEN"
    }
  }
}
```

Raw secret status:

- `dogfood-secret` was not written to the usage event
- `dogfood-secret` was not written to replay metadata
- `dogfood-secret` was not written to ledger output

Replay result:

- `replayable`: `true`
- `exact_replay_metadata_ready`: `true`
- `executed`: `true`
- replay body: `{ "authorized": true }`

## What This Proves

API2Agent can now treat credentials as local execution rights:

```text
provider auth metadata
  -> local credential resolver
  -> injected request patch
  -> provider execution
  -> credential_reference in usage event
  -> replay with redacted metadata
```

This completes the first local implementation of Credential Schema v0.1 + Local Resolver.

## Limits

- config credentials are supported by resolver API but not yet wired to a CLI config file
- proxy-side credential injection is not implemented yet
- hosted vault is intentionally out of scope
- OAuth is modeled but not implemented
