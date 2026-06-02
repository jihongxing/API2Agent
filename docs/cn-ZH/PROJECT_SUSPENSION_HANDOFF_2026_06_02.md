# API2Agent 项目阶段性挂起交接 - 2026-06-02

## 挂起结论

当前项目可以阶段性挂起。

阶段判断：

```text
Agent Capability Compiler 在当前 RC 范围内已经完整，可以暂停继续扩展。
```

当前最重要的未完成工作不是继续写 compiler，而是等待真实用户 onboarding feedback，并把反馈转成小范围 RC3.x 修复。

## 当前 Git 状态

挂起时基准：

```text
branch: master
worktree: clean
latest commit: 3f7116b Clarify RC3 onboarding first demo
```

最近关键提交：

```text
3f7116b Clarify RC3 onboarding first demo
8866417 Release v0.1.0rc3
19e4602 Clarify RC2 release surface and onboarding dogfood
576c7a8 Fix package version metadata alignment
c2d8e53 Add next session handoff after RC2 release
d7aaf7b Release v0.1.0rc2
```

注意：

```text
v0.1.0rc3 tag 指向 8866417。
master 在 tag 之后还有 3f7116b 文档修复。
```

这意味着 GitHub Release 资产仍是 RC3 wheel/sdist，没有重新构建；README 和 Quickstart 的 first-demo 文档在 `master` 上更新过。

## 当前公开 Release

GitHub Release：

```text
https://github.com/jihongxing/API2Agent/releases/tag/v0.1.0rc3
```

Release 状态：

```text
tag: v0.1.0rc3
draft: false
prerelease: true
published: 2026-06-02T11:36:05Z
targetCommitish: master
```

Release assets：

```text
api2agent-0.1.0rc3-py3-none-any.whl
sha256: ab6080361853a8334ec6d3d268b512b020b40ced118167da591a579a2f37d007

api2agent-0.1.0rc3.tar.gz
sha256: 81ff5d7045c1d3f6a5eaf148d4b22ad6bce0c92ffa4761b2a66e9c8de12fea84
```

推荐 tester 安装目标：

```bash
python -m pip install https://github.com/jihongxing/API2Agent/releases/download/v0.1.0rc3/api2agent-0.1.0rc3-py3-none-any.whl
```

不要再给测试用户 RC2。

## 已完成判断

### Agent Capability Compiler

结论：

```text
完整到足够进入 RC 真实用户路径。
```

当前支持来源：

- OpenAPI
- curl
- HAR
- Postman Collection
- Insomnia export
- Bruno collection
- protobuf/gRPC scaffold
- AsyncAPI HTTP webhook
- workflow endpoint manifest
- GraphQL endpoint manifest

当前生成物主路径：

- `capability.json`
- `tools.json`
- `diagnostics.json`
- `auth.env.example`
- generated `README.md`
- `runner.py`
- `smoke_test.py`
- `manual_write_test.py`
- `mcp_server.py`
- OpenAI example
- Claude Desktop MCP config example

不要默认继续增加 source adapter。

### RC2 -> RC3 修复

RC2 dogfood 发现：

```text
package metadata 是 0.1.0rc2，但 api2agent.__version__ 是 0.1.0。
```

已在 RC3 修复：

```text
api2agent.__version__ == 0.1.0rc3
importlib.metadata.version("api2agent") == 0.1.0rc3
```

新增守护测试：

```text
tests/test_version.py
```

### Onboarding first demo 修复

RC3 发布后继续修了 docs：

- README 从 `RC2 status` 改成 `RC3 status`
- README first demo 改为不依赖源码仓库 fixture
- Quickstart 统一使用真实 console script：`api2agent`
- Quickstart 首个 demo 改成 wheel-only 可执行路径
- 明确 curl first demo 的 `diagnostics warn score=90` 是预期，不是失败

当前 first demo：

```bash
api2agent generate --curl="curl https://api.github.com/rate_limit" --name github_rate_limit --provider-region global --output api2agent-output --force
api2agent inspect api2agent-output
api2agent diagnose api2agent-output
api2agent test api2agent-output
```

公共 RC3 wheel 真实安装后已验证这条路径能走通，`api2agent test` 返回 GitHub rate_limit `200`。

## 已通过验证

RC3 发布前：

```text
python -m pytest
290 passed
```

RC3 public URL install 后：

```text
api2agent.__version__ == 0.1.0rc3
importlib.metadata.version("api2agent") == 0.1.0rc3
```

真实路径已通过：

- GitHub rate_limit OpenAPI dogfood
- GitHub rate_limit curl first demo
- ipify curl
- GitHub rate_limit + ipify Postman collection
- ipify HAR capture
- generated runner/MCP/OpenAI examples compile
- OpenAI example 缺少 SDK 时给出预期安装提示

最新 docs 修复后：

```text
git diff --check
passed
```

## 已知非阻塞问题

### 1. curl first demo 会 warn

现象：

```text
Diagnostics: warn score=90 errors=0 warnings=1 info=1
weak_tool_description
```

判断：

```text
预期内，不是 compiler failure。
```

原因是 curl 没有 OpenAPI 的 operation summary/description。真实接 Agent 前应优先使用 OpenAPI，或接受 diagnostics 提醒。

### 2. 公开示例 API 不稳定

之前 dogfood 看到过：

- Swagger Petstore `404`
- httpbin `503`

判断：

```text
这类 live HTTP failure 不能自动归因到 compiler。
```

恢复项目时要继续把 live API availability 和 compiler correctness 分开判断。

### 3. Fixture collection 不适合直接给外部 tester

仓库 fixture 里有 `api.example.com` 和 fake auth，用来做 parser/generator regression，不适合当外部测试入口。

外部 tester 应先跑 GitHub rate_limit first demo，然后换成自己的 OpenAPI/Postman/HAR/curl。

### 4. PyPI/TestPyPI 未启用

当前公开安装入口是 GitHub Release wheel。

是否启用 TestPyPI/PyPI，应该等 2-3 个真实用户反馈之后再决定。

## 挂起期间外部测试建议

给测试用户的最小任务：

```bash
python -m pip install https://github.com/jihongxing/API2Agent/releases/download/v0.1.0rc3/api2agent-0.1.0rc3-py3-none-any.whl
api2agent --help
api2agent generate --curl="curl https://api.github.com/rate_limit" --name github_rate_limit --provider-region global --output api2agent-output --force
api2agent inspect api2agent-output
api2agent diagnose api2agent-output
api2agent test api2agent-output
```

然后让 tester 换成自己的输入来源：

- OpenAPI spec
- Postman Collection
- HAR capture
- curl command

反馈时至少记录：

- 操作系统和 Python 版本
- 安装命令
- 输入来源类型
- 完整命令
- 完整输出
- 卡在哪一步：install / help / generate / inspect / diagnose / test / runner / MCP / OpenAI example
- 是否愿意提供脱敏后的 spec/collection/HAR/curl

## 恢复项目时第一步

恢复时先不要直接写功能。按顺序做：

1. 读本文件。
2. 跑：

```bash
git status --short
git log --oneline -8
```

3. 确认 release 仍可见：

```bash
gh release view v0.1.0rc3 --repo jihongxing/API2Agent --json tagName,url,assets,isDraft,isPrerelease,publishedAt,targetCommitish
```

4. 重新跑 public-wheel first demo，必须在仓库外目录执行，避免本地源码 shadow installed package。
5. 汇总外部 tester 反馈。
6. 只把真实反馈分成 RC3.x 小修复。

## 恢复后的优先级

优先级 1：

```text
RC3.x real-user onboarding fixes
```

只修：

- install/package metadata 问题
- CLI help / command UX
- docs 指引错误
- generated README 可读性
- diagnostics 文案误导
- safe read-only smoke 问题
- runner/MCP/OpenAI example first-mile 问题

优先级 2：

```text
决定 TestPyPI/PyPI 发布策略
```

前提：至少有 2-3 个真实用户完成或卡住 onboarding，并且卡点已分级。

优先级 3：

```text
回到 Hosted Control Plane / Go Control Plane hosted-readiness backlog
```

只有当 release surface 稳定，且 roadmap 明确切回 Hosted Control Plane 时再做。

## 暂停期间不要启动

除非先更新 roadmap，不要启动：

- 新 source adapter 横向扩展
- workflow runtime
- event bus
- gRPC runtime transport
- hosted SaaS 新阶段
- marketplace
- billing
- provider revenue share
- OAuth/OIDC hosted auth
- public Control Plane CRUD
- production Data Plane deployment
- automatic snapshot publish/reload

## 下一次推荐任务

如果恢复时已经有真实用户反馈：

```text
整理 RC3 外部测试反馈 -> 生成 RC3.1 修复清单 -> 只修 P0/P1。
```

如果恢复时还没有真实用户反馈：

```text
完成 RC3 外部测试包：tester guide、反馈模板、问题分级规则。
```

如果决定彻底切回平台方向：

```text
先更新 roadmap，再回到 Go Control Plane Hosted Admin Gateway Permission Source Design v0。
```

## 最后一条判断

这个项目现在不是“做不下去”而挂起。

它是到了一个合理的产品验证暂停点：compiler 已经足够完整，继续写代码的边际收益低于让真实用户走一遍 onboarding。
