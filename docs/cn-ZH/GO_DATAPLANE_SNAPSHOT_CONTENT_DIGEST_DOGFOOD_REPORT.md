# Go Data Plane Snapshot Content Digest Dogfood 报告

日期：2026-05-31

## 目标

即使 snapshot metadata 看起来仍然一致，也要发现 snapshot 文件内容被篡改。

上一层 guard 检查 metadata agreement。这一层 guard 检查真实的 `snapshot.json` 文件字节。

## 已实现

Control Plane snapshot artifact 现在包含：

```json
{
  "snapshot_digest": "sha256:..."
}
```

digest 会记录在：

- `manifest.json`
- distribution `current.json`

Control Plane 会在 publish artifact 前校验 digest。Data Plane 会在加载 distributed snapshot 前校验 digest。

## 已验证流程

cross-plane dogfood 现在会验证：

1. 发布一个合法的 v6 artifact。
2. 对 distribution 中的 v6 `snapshot.json` 追加空白字符。
3. Data Plane reload 因文件 digest 不匹配 `manifest.json` 而拒绝 v6。
4. active serving snapshot 仍然保持 v2。
5. v7 artifact 在 publish 前被修改。
6. Control Plane 拒绝 v7 publish，且不会推进 `current.json`。

## 检查项

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

## 结果

Snapshot Artifact Content Digest Guard v0 通过。

本地 distribution path 现在可以同时拒绝 metadata drift 和原始文件内容 drift。
