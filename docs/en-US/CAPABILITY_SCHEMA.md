# Capability Schema

## 1. Purpose

Capability Schema defines the unit that can become comparable, routable, and eventually marketable.

An API endpoint is not enough. A capability must describe the Agent intent that multiple providers can fulfill.

## 2. Minimal Objects

### Capability

```json
{
  "id": "image_generation",
  "name": "Image Generation",
  "description": "Generate an image from a text prompt.",
  "input_schema": {},
  "output_schema": {},
  "safety": "write"
}
```

### Provider Candidate v0.2

```json
{
  "id": "provider_a_image_generation",
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "tool_id": "generate_image",
  "estimated_cost": 0.02,
  "output_mapping": {}
}
```

### Metrics Snapshot

```json
{
  "capability_id": "image_generation",
  "provider_id": "provider_a",
  "total_calls": 100,
  "successful_calls": 92,
  "failed_calls": 8,
  "success_rate": 0.92,
  "average_latency_ms": 1200,
  "estimated_cost_per_call": 0.02
}
```

## 3. Comparability Rules

Two providers can be compared under the same capability only if:

- they share the same `capability_id`
- they accept compatible inputs
- they return compatible outputs
- they have compatible safety expectations
- their metrics are measured on the same fulfillment intent

Do not compare providers only because their endpoints look similar.

Example:

```text
GET /images/{id}
POST /generate-image
```

These are not automatically comparable. One is retrieval, the other is generation.

## 4. Routing Inputs

Routing v0 can use:

- provider candidates
- usage-derived metrics
- estimated cost
- routing strategy

Routing v0 does not yet execute the selected provider. It only selects and ranks providers.

## 5. What v0 Does Not Solve

Capability Schema does not yet solve:

- semantic auto-mapping from arbitrary APIs
- output quality evaluation
- provider onboarding
- pricing contracts
- marketplace trust review
- routing execution

Those come after the schema is stable enough to dogfood.

## 6. v0.2: Output Normalization Metadata

Routing execution requires stable capability output. Different providers can fulfill the same capability while returning different raw response shapes.

Example:

```text
Capability: public_ip_lookup
```

ipify returns:

```json
{
  "ip": "108.174.61.76"
}
```

httpbin returns:

```json
{
  "origin": "108.174.61.76"
}
```

Both should normalize to:

```json
{
  "ip": "108.174.61.76"
}
```

Provider candidates therefore need `output_mapping`:

```json
{
  "id": "ipify_public_ip",
  "capability_id": "public_ip_lookup",
  "provider_id": "ipify",
  "tool_id": "get",
  "estimated_cost": 0.001,
  "output_mapping": {
    "ip": "$.ip"
  }
}
```

```json
{
  "id": "httpbin_public_ip",
  "capability_id": "public_ip_lookup",
  "provider_id": "httpbin",
  "tool_id": "get_ip",
  "estimated_cost": 0.002,
  "output_mapping": {
    "ip": "$.origin"
  }
}
```

Supported mapping syntax in v0.2:

- `$` maps the whole response.
- `$.field` maps a top-level field.
- `$.a.b.c` maps a nested field.

Unsupported in v0.2:

- arrays
- filters
- transforms
- type coercion
- fallback expressions

This is intentionally small. The goal is to make routing execution possible without adding LLM-based response transformation yet.
