# Credential Policy Dogfood Report

日期：2026-05-30

## 目的

验证多个 credentials 都能满足同一个 provider 时，credential resolution 仍然是确定性的。

## Policy

Credential source precedence：

```text
inline override -> config credential -> request credential/env intent -> none
```

Config owner precedence：

```text
exact project owner -> local project owner -> first matching config credential
```

## 结果

- inline credentials 会覆盖 config 和 request credentials
- config credentials 会覆盖 request/env intent credentials
- project-owned config credentials 会覆盖 local fallback credentials
- local fallback credentials 会覆盖 unrelated owner credentials
- redacted metadata 会保留被选中的 `owner_id`

## 测试

```text
pytest tests/test_credentials.py tests/test_control_layer.py
26 passed
```

## 产品结论

这让 credential orchestration 对本地 BYOK 来说足够可预测：

- proxy 可以无歧义地选择 credential
- usage attribution 可以解释是谁提供了这个 credential
- 未来 hosted identity 可以替换 local owner matching，而不需要改变基础 resolver contract
