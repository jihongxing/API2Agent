# API2Agent Generated Package Region Metadata Report v0

日期：2026-05-31

状态：已完成

## 总结

Generated packages 现在可以携带可选 provider-region intent，而且不改变 routing behavior。

这是一个 metadata-only 的 Tooling Layer 改动：

- API-first only
- 不做 workflow engine
- 不做 routing rewrite
- 不做 marketplace 或 billing
- 不做 credential vault

## 改动

### CLI Metadata Input

`api2agent generate` 现在支持：

```bash
api2agent generate \
  --curl "curl https://api.example.com/items" \
  --name example_items \
  --provider-region us-east
```

生成的 `capability.json` 包含：

```json
{
  "provider_region": "us-east",
  "provider_regions": ["us-east"]
}
```

### Generated README Guidance

Generated package README files 现在包含 Provider Region section。

配置 region metadata 后，README 会展示 generated provider-region intent，并说明可以通过 runtime env 覆盖：

```bash
API2AGENT_PROVIDER_REGION=us-east
```

### Proxy Payload Propagation

Generated runners 现在会在 proxy payload 中包含 `provider_region`：

```json
{
  "provider_id": "example_items",
  "provider_region": "us-east"
}
```

`API2AGENT_PROVIDER_REGION` 会覆盖 generated metadata。这样本地或区域 dogfoods 可以不重新生成 package 就传入 region。

## Dogfood

复现命令：

```bash
python scripts/api2agent_generated_region_metadata_dogfood.py
```

产物：

```text
.dogfood/generated-region-metadata/result.json
```

Dogfood checks：

- `capability.provider_region == "us-east"`
- `capability.provider_regions == ["us-east"]`
- generated runner proxy payload 包含 `provider_region == "us-east"`
- scope 保持 API-first

## 测试

新增 regression coverage：

- CLI 把 provider-region metadata 写入 generated `capability.json`
- generated runner proxy payload 包含 provider region
- `API2AGENT_PROVIDER_REGION` runtime override 优先于 generated metadata
- generated README 记录 provider-region intent

已验证：

```text
python scripts/api2agent_generated_region_metadata_dogfood.py
python scripts/api2agent_tooling_baseline_audit.py
python -m pytest tests/test_cli.py tests/test_runner_generation.py tests/test_generators.py
```

## 剩余缺口

下一项 Tooling Re-entry 缺口是 authenticated proxy dogfood coverage。

Baseline audit 已验证 no-auth proxy paths 和 direct bearer execution，但刻意没有让 bearer calls 通过 proxy credential config。下一项任务应该在不引入 credential vault 的前提下补上这条 observable-path gap。

下一项任务：

```text
Proxy-mode Credential Dogfood Expansion v0
```

