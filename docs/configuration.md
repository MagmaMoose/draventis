# Configuration

There are two layers:

1. **`targets.yaml`**: what dastgate itself reads (the scan config). In a
   cluster the Helm chart renders it into a ConfigMap and mounts it at
   `/config/targets.yaml`.
2. **Chart `values.yaml`**: how you configure the Helm release; the chart
   translates the relevant values into `targets.yaml`.

## `targets.yaml`

```yaml
defaults:                     # applied to every target that omits the field
  policy: baseline
  schedule: nightly
  tags: [dast]

defectdojo:                   # the reimport sink (enabled by presence of `url`)
  url: https://defectdojo.example.com
  product_type: MyOrg         # optional grouping in DefectDojo
  engagement_prefix: "DAST - "
  auto_create_context: true   # DefectDojo creates product/engagement/test
  close_old_findings: true    # fixed alerts auto-mitigate per engagement
  tags: [dast]

nuclei:
  enabled: true

targets:
  - name: my-site             # required; also the default product name
    url: https://my-site.example.com   # required
    policy: baseline          # baseline | full | api
    schedule: nightly         # nightly | weekly
    product: myorg/site       # optional DefectDojo product name
    openapi: https://…/openapi.json    # optional; enables api/openapi scanning
    tags: [prod]              # optional extra DefectDojo tags
    auth:                     # optional
      type: browser-oidc      # none | browser-oidc
      login_url: https://my-site.example.com/login
      user_env: ZAP_USER      # env var holding the username
      pass_env: ZAP_PASS      # env var holding the password
```

### Fields

| Field | Default | Notes |
|---|---|---|
| `name` | - | **Required.** Unique per config. |
| `url` | - | **Required.** The target base URL. |
| `policy` | `baseline` | `baseline` (passive), `full` (active), `api` (OpenAPI). |
| `schedule` | `nightly` | Which CronJob runs it. |
| `product` | `name` | DefectDojo product name. |
| `openapi` | - | Spec URL; seeds the `api` (ZAP) scan. |
| `tags` | `defaults.tags` | Extra DefectDojo tags. |
| `auth.type` | `none` | `browser-oidc` is accepted, but the shipped AF plans don't yet drive it. See the note below. |
| `auth.user_env` / `auth.pass_env` | `ZAP_USER` / `ZAP_PASS` | Env vars the creds are read from. |

!!! note "Authenticated scanning is not fully wired yet"
    dastgate parses `auth` and exports `DASTGATE_LOGIN_URL` / the credential env
    vars into the scan environment, but the shipped AF plans in `automation/` do
    not yet contain an `authentication` block, so they scan unauthenticated. To
    scan behind an OIDC login today, add an `authentication` (browser method) +
    `verification` block to the plan yourself. See [Design](design.md).

### Secrets are not in this file

The DefectDojo token and scan credentials come from the **environment**, never
from `targets.yaml` and never from a scanned response:

| Env var | Purpose |
|---|---|
| `DEFECTDOJO_TOKEN` | DefectDojo API token (upload auth). |
| `DEFECTDOJO_URL` | Optional; overrides / provides `defectdojo.url`. |
| `ZAP_USER` / `ZAP_PASS` | Per the target's `auth.*_env`. |

If `defectdojo.url` is set but `DEFECTDOJO_TOKEN` is empty, uploads are skipped
(with a warning). Scans still run.

## Chart values → `targets.yaml`

The chart builds the `defaults`, `defectdojo`, `nuclei`, and `targets` blocks
from these values:

| Chart value | `targets.yaml` |
|---|---|
| `defaults` | `defaults:` |
| `defectDojo.url` / `.productType` / `.engagementPrefix` / `.autoCreateContext` / `.closeOldFindings` / `.tags` | `defectdojo:` |
| `nuclei.enabled` | `nuclei.enabled` |
| `targets` | `targets:` |

Secrets are supplied separately (`secret.*` or `externalSecret.*`) and reach the
container as env vars. See [Deployment](deployment.md). The full annotated
values file is [`charts/dastgate/values.yaml`](https://github.com/MagmaMoose/dastgate/blob/main/charts/dastgate/values.yaml).

## Scan policies

| Policy | ZAP plan | Destructive? | Point it at |
|---|---|---|---|
| `baseline` | `automation/zap-baseline.yaml` | No (passive) | production or staging |
| `full` | `automation/full-active.yaml` | **Yes** (active) | **staging only** |
| `api` | `automation/api-scan.yaml` | Yes (active) | staging services with a spec |

For `full`/`api` targets, Nuclei (when enabled) also runs with `-dast` fuzzing.
Never point an active policy at production.
