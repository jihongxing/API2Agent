# API2Agent Proxy-mode Credential Dogfood Expansion 报告 v0

日期：2026-05-31

状态：已完成

## 总结

Authenticated API 的 generated packages 现在可以通过 proxy mode + local credential config 完成 dogfood，同时 provider secrets 不会进入 generated package、proxy payload、usage event 或 dogfood report。

这补齐了 Tooling Re-entry 阶段 authenticated proxy 的缺口，并且不改变当前边界：

- API-first only
- 不做 workflow engine
- 不做 marketplace 或 billing
- 不做 credential vault
- 只使用 local proxy 和 local provider stub

## 已验证内容

新增 dogfood script 会跑通这条本地路径：

```text
generated curl package
  -> generated runner proxy mode
  -> local API2Agent proxy
  -> local credential config resolver
  -> local authenticated provider stub
  -> SQLite usage event
```

Generated package 只发送 credential intent。请求侧 credential env var 会刻意缺失。Proxy 会解析 config credential，把 `Authorization: Bearer ...` 注入 provider request，并且只记录 credential-safe attribution。

## Dogfood

复现命令：

```bash
python scripts/api2agent_proxy_credential_dogfood.py
```

产物：

```text
.dogfood/proxy-credential/result.json
```

Dogfood checks：

- generated runner 返回 successful proxied response
- local provider 只被调用一次
- proxy 注入 config-sourced bearer credential
- 记录一个 proxy usage event
- usage event 记录 `credential_reference == "config:cred_proxy_dogfood"`
- credential metadata 记录 source、scope、status 和 rotation hint
- generated provider region 被记录为 `local`
- raw secret 不写入 usage events 或 dogfood report output
- 不需要 request-side credential secret
- scope 保持 API-first 和 no-vault

## 结果

Dogfood 已通过。

关键观测值：

```json
{
  "credential_reference": "config:cred_proxy_dogfood",
  "provider_region": "local",
  "execution_mode": "proxy",
  "success": true
}
```

## 为什么重要

这项任务证明 API2Agent 可以让 generated packages 保持轻量，同时让 authenticated calls 进入 proxy 的可观测路径。

这直接服务当前 Tooling Layer 目标：

- 更多真实调用数据：authenticated calls 可以进入 usage/ledger
- 更低接入成本：开发者不需要手改 generated runner source
- 更快的未来 routing：credential-safe usage events 已保留 provider/region metadata，后续可用于 latency comparison

## 剩余缺口

下一项 Tooling Re-entry 缺口是 generated packages 的速度测量。

Region metadata 已经存在，authenticated proxy dogfood 也已经覆盖。下一项任务应该让 generated packages 可以测量 direct/proxy latency，并输出 p50/p95。

下一项任务：

```text
Generated Package Latency Benchmark Helper v0
```
