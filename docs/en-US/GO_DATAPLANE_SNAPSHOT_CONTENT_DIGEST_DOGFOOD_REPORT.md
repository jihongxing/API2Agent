# Go Data Plane Snapshot Content Digest Dogfood Report

Date: 2026-05-31

## Goal

Detect snapshot file tampering even when snapshot metadata still looks consistent.

The previous guard checked metadata agreement. This guard checks the actual `snapshot.json` bytes.

## Implemented

Control Plane snapshot artifacts now include:

```json
{
  "snapshot_digest": "sha256:..."
}
```

The digest is recorded in:

- `manifest.json`
- distribution `current.json`

Control Plane validates the digest before publishing an artifact. Data Plane validates the digest before loading a distributed snapshot.

## Verified Flow

The cross-plane dogfood now verifies:

1. A valid v6 artifact is published.
2. The distributed v6 `snapshot.json` is modified by appending whitespace.
3. Data Plane reload rejects v6 because the file digest no longer matches `manifest.json`.
4. The active serving snapshot remains v2.
5. A v7 artifact is modified before publish.
6. Control Plane rejects v7 publish before advancing `current.json`.

## Checks

```json
{
  "content_digest_reload_rejected": true,
  "content_digest_reload_kept_v2": true,
  "content_digest_reload_audit_event_recorded": true,
  "health_after_content_digest_reload_still_v2": true,
  "content_digest_publish_rejected": true,
  "content_digest_publish_did_not_advance_current": true
}
```

## Result

Snapshot Artifact Content Digest Guard v0 passed.

The local distribution path now rejects metadata drift and raw file content drift.
