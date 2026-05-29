# API2Agent Dogfood Report

## 1. Goal

The goal of this dogfood round is not to prove that every API works perfectly. The goal is to use real APIs to expose what Phase 2 should solve.

Validation path:

```text
Real OpenAPI / real curl
  -> api2agent generate
  -> api2agent inspect
  -> api2agent test
```

## 2. Samples

| Sample | Type | Goal |
|--------|------|------|
| Swagger Petstore | OpenAPI | small public OpenAPI |
| GitHub REST API | OpenAPI | large real OpenAPI |
| httpbin curl POST | curl | query/header/json body inference |
| GitHub rate_limit curl | curl | read endpoint + Bearer auth scenario |

## 3. Summary

| Sample | Generate | Inspect | Test | Result |
|--------|----------|---------|------|--------|
| Swagger Petstore | pass | pass | fail | relative server URL and auth handling need work |
| GitHub REST API | pass | pass | pass | large spec works, but output is too large |
| httpbin curl POST | pass | pass | skipped | safety policy correctly blocks write smoke test |
| GitHub public curl | pass | pass | pass | curl read happy path works |
| GitHub auth curl | pass | pass | fail | Bearer auth detected, but env/name are too generic |

## 4. Detailed Observations

### 4.1 Swagger Petstore

Input:

```text
https://petstore3.swagger.io/api/v3/openapi.json
```

Result:

- `generate` passed
- `inspect` passed
- tools and schemas were readable
- `test` failed

Failure 1:

```text
missing_auth: SWAGGER_PETSTORE_OPEN_API_3_0_API_KEY
```

Reason:

The parser currently promotes any detected security scheme to capability-level auth. Real OpenAPI specs often have endpoint-specific auth requirements.

Failure 2:

After providing a dummy key:

```text
Request URL is missing an 'http://' or 'https://' protocol.
```

Reason:

Petstore uses a relative server URL:

```text
/api/v3
```

The current runner needs an absolute base URL.

### 4.2 GitHub REST API

Input:

```text
https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json
```

Result:

- `generate` passed
- `inspect` passed
- `test` passed
- smoke test called `GET /` and returned 200

Observations:

- Large specs can generate.
- Generation took about 25 seconds.
- Inspect output is too large for humans.
- Exposing all tools directly to an Agent is not realistic.

### 4.3 httpbin curl POST

Input:

```powershell
api2agent generate '--curl=curl https://httpbin.org/anything?verbose=true -H "X-Trace-Id: trace-123" --json "{\"name\":\"demo\",\"active\":true}"'
```

Result:

- `generate` passed
- `inspect` passed
- query/header/body inference worked
- `test` skipped

Inspect output:

```text
- post_anything: POST /anything [write] required=body
  query: verbose string default=true
  header: X-Trace-Id string default=trace-123
  body: object {name:string, active:boolean} required
```

Test output:

```text
No read-only endpoint was detected. Add a manual test before calling write/delete tools.
```

Conclusion:

This is the correct default safety behavior. Write endpoints should not be smoke-tested automatically.

### 4.4 GitHub curl

Public read endpoint:

```text
curl https://api.github.com/rate_limit
```

Result:

- `generate` passed
- `test` passed
- returned 200

Bearer auth curl:

```text
curl https://api.github.com/rate_limit -H "Authorization: Bearer ghp_fake"
```

Result:

- Bearer auth detected
- `inspect` showed `Auth: bearer via Authorization`
- `test` failed on missing env, which is correct

Issue:

Generated capability name:

```text
api
```

Generated env:

```text
API_TOKEN
```

Reason:

The curl parser currently infers the name from the first host segment, so `api.github.com` becomes `api`.

## 5. Recommended Phase 2 Priorities

### P0: Tool Filtering / Selection

GitHub REST API proves large specs can generate, but dumping every endpoint into an Agent is not usable.

Recommendations:

- `--include-tag`
- `--include-path`
- `--include-operation`
- `--max-tools`
- inspect should default to summary, not full tool dump

### P0: Endpoint-level Auth

Petstore exposed that capability-level auth is too coarse.

Recommendations:

- Add auth override to tools in the IR.
- Parse global/path/operation security.
- Let smoke test choose a read endpoint that does not require auth.
- Require env only when the selected endpoint needs auth.

### P1: Base URL Override

Relative server URLs exist in real specs.

Recommendations:

- `api2agent generate spec.json --base-url https://petstore3.swagger.io/api/v3`
- Give clear errors for relative server URLs.
- Infer origin when the spec is downloaded from a URL.

### P1: Manual Write Tool Test

curl POST can generate, but smoke test skips it by default. That is safe, but users still need a verification path.

Recommendations:

- `api2agent test --allow-write`
- Generate manual write test examples in README.
- Clearly warn for write/delete operations.

### P1: curl Naming

`api.github.com` -> `api` is too generic, hurting env and package readability.

Recommendations:

- For `api.{domain}.com`, use `{domain}`.
- For `{service}.com`, use `{service}`.
- Support and document `--name`.

### P2: Large Spec Performance

GitHub spec generation took about 25 seconds.

Recommendations:

- Profile parser/generator.
- Lazy schema formatting.
- Limit generation by selected tools.
- Avoid expensive full inspect output.

## 6. Conclusion

The MVP path is valid:

```text
OpenAPI/curl -> IR -> capability package -> smoke test / MCP server
```

But Phase 2 should not start by adding more input formats.

The next phase should improve real API usability:

1. tool filtering
2. endpoint-level auth
3. base URL override
4. manual write test
5. curl naming

