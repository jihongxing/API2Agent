# Go Control Plane Hosted Admin Gateway Permission Source Implementation 报告 v0

日期：2026-06-01

状态：complete

## 摘要

hosted admin gateway contract harness 现在实现了本地 permission source boundary。public dogfood bearer tokens 会先解析成 project-scoped trusted admin claims，然后才允许转发到私有 Control Plane。

这让 Control Plane trusted-gateway authenticator 继续作为第二道 authorization gate，同时证明 gateway-side permission issuance、denial、route mapping、trusted header stripping 和 secret-safe evidence。

## 已实现

- 在 local hosted admin gateway harness 中加入显式 `GatewayPermissionDecision` contract。
- 加入 static dogfood permission source，包含 `policy_source`、`policy_version`、roles、project scope 和 permission claims。
- 将 hosted admin method/path 映射到现有 Control Plane permission constants：
  - `POST /v1/admin/registry/validate`
  - `POST /v1/admin/registry/import-replace`
  - `POST /v1/admin/snapshots/export-artifact`
  - `GET /v1/admin/distribution/current`
  - `POST /v1/admin/distribution/publish`
- public `Authorization` 只在 gateway 本地消费，Control Plane 只收到 gateway-issued trusted headers。
- 保留 `X-Request-ID` 和 `Idempotency-Key` forwarding。
- 增加 fail-closed gateway-local errors：
  - `PUBLIC_AUTH_REQUIRED`
  - `PUBLIC_AUTH_INVALID`
  - `PERMISSION_SOURCE_UNAVAILABLE`
  - `PUBLIC_AUTHZ_DENIED`
  - `PUBLIC_ROUTE_NOT_FOUND`
  - `PUBLIC_METHOD_NOT_ALLOWED`
- 增加强制 insufficient trusted-permission path，证明 Control Plane 仍会作为第二道 gate 返回 `403 AUTHZ_DENIED`。
- 增加 regression tests，覆盖 permission decisions、failure typing、trusted header injection、public header stripping 和 endpoint permission mapping。

## Dogfood 证据

Live dogfood 已通过：

```text
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

报告记录：

- `status=passed`
- `admin_audit_events=3`
- `idempotency_records=1`
- missing public auth 返回 `401 PUBLIC_AUTH_REQUIRED`
- invalid public auth 返回 `401 PUBLIC_AUTH_INVALID`
- permission source unavailable 返回 `503 PERMISSION_SOURCE_UNAVAILABLE`
- readonly validate 成功
- readonly import/replace 在 gateway 本地以 `403 PUBLIC_AUTHZ_DENIED` 失败
- forced insufficient trusted permissions 到达 Control Plane，并返回 `403 AUTHZ_DENIED`
- raw public tokens 和 gateway secret 未出现在 audit/idempotency/report evidence 中

## 验证

已通过：

```text
python -m py_compile scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -m pytest tests/test_go_control_plane_hosted_admin_gateway_contract.py
python -c "import importlib.util, sys; p='scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py'; s=importlib.util.spec_from_file_location('harness', p); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); m.assert_contract_helpers(); print('contract helpers passed')"
python scripts/go_control_plane_hosted_admin_gateway_contract_dogfood.py --output .dogfood/go-control-plane-hosted-admin-gateway-permission-source/report.json
```

## 保持不做的事项

未新增 OAuth/OIDC、login/session lifecycle、public CRUD、invitation management、marketplace/provider onboarding、credential vault、billing、workflow runtime、production gateway deployment、automatic propagation 或 Data Plane mutable table reads。

## 下一项建议任务

```text
Go Control Plane Hosted Admin Gateway Permission Source Closeout + Phase Review v0
```
