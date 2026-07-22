# dastgate

[![CI](https://github.com/MagmaMoose/dastgate/actions/workflows/ci.yml/badge.svg)](https://github.com/MagmaMoose/dastgate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Scheduled **DAST** (Dynamic Application Security Testing) for Kubernetes.
[**OWASP ZAP**](https://www.zaproxy.org/) (driven by the ZAP Automation
Framework) + [**Nuclei**](https://github.com/projectdiscovery/nuclei) run on a
schedule against your already-deployed targets, with results reimported into
[**DefectDojo**](https://www.defectdojo.org/).

Deploy it to any cluster with Helm, point it at your URLs, and it does the rest.

```bash
helm install dastgate ./charts/dastgate \
  --namespace security --create-namespace \
  --set defectDojo.url=https://defectdojo.example.com \
  --set secret.defectDojoToken=$DEFECTDOJO_TOKEN \
  --set targets[0].name=my-site \
  --set targets[0].url=https://my-site.example.com \
  --set targets[0].policy=baseline
```

---

## Why DAST

Static analysis (SAST/SCA/IaC/secrets) reasons about **source and artifacts at
rest**. It never sends an HTTP request to a running instance. DAST closes the
"does the deployed thing actually behave insecurely?" gap:

- **AuthN / session**: cookie flags, session fixation, IDOR across users.
- **Injection reachable at runtime**: confirmed SQLi/XSS with a working payload.
- **Response headers / TLS / cookies**: the actual `CSP`, `HSTS`, `Secure`/
  `HttpOnly`/`SameSite` your ingress and app emit at runtime.
- **CORS misconfiguration**, **SSRF/OOB**, live **API surface** from an OpenAPI
  spec, and **config drift** between the repo and what's actually deployed.

## How it works

dastgate is an **orchestrator + uploader**. The scanner is the engine, dastgate
schedules it and ships the results:

```
CronJob (nightly / weekly)
  └─ dastgate run --schedule <name>
       ├─ for each target in targets.yaml:
       │    ├─ ZAP  (Automation Framework plan chosen by policy) → report.xml
       │    └─ Nuclei (optional)                                 → report.jsonl
       └─ reimport each report → DefectDojo /api/v2/reimport-scan/
```

- Runs as one or more **Kubernetes CronJobs**, because DAST needs a *running
  target*. Your cluster already runs your apps.
- The DefectDojo client is **stdlib `urllib` and failure-isolated**: an upload
  error is logged and never fails the scan.
- **Reimport, not import**: DefectDojo dedupes against the existing test,
  reactivates regressions, and (with `close_old_findings`) mitigates alerts that
  disappeared, giving "what's new / fixed since last scan" without a merge-base
  diff. See [`docs/design.md`](docs/design.md) for why DAST is baseline-only, not
  diff-gated.

## Scan policies

| Policy | ZAP jobs | Destructive? | Point it at |
|---|---|---|---|
| `baseline` | spider + **passive** only | No | production or staging |
| `full` | baseline + ajax-spider + **active** attacks | **Yes** | **staging only** |
| `api` | OpenAPI import → spider → active | Yes | staging services with a spec |

Each policy maps to a ZAP Automation Framework plan in [`automation/`](automation/).

## Configuration

Targets are declared in `targets.yaml` (rendered by the Helm chart from
`values.yaml`, or supplied directly):

```yaml
defectdojo:
  url: https://defectdojo.example.com   # sink enabled by presence of a URL
nuclei:
  enabled: true
targets:
  - name: my-site
    url: https://my-site.example.com
    policy: baseline          # passive, production-safe
    schedule: nightly
  - name: app-staging
    url: https://app.staging.example.com
    product: example/app      # DefectDojo product name
    policy: full              # active scan, staging only
    schedule: weekly
    openapi: https://app.staging.example.com/openapi.json
    auth:
      type: browser-oidc      # drive a real OIDC login headlessly
      login_url: https://app.staging.example.com/login
      user_env: ZAP_USER      # credentials come from the environment/Secret
      pass_env: ZAP_PASS
```

Secrets (the DefectDojo token, scan credentials) come from the environment:
either a plain Kubernetes Secret (default) or
[External Secrets Operator](https://external-secrets.io/) (optional). They are
**never** read from a scanned response. Full reference:
[`docs/configuration.md`](docs/configuration.md).

## Authenticated scanning

Apps behind an OIDC proxy need dastgate to authenticate. The config model accepts
per-target `auth` (and dastgate exports the login URL + credentials into the
scan environment), but **the shipped AF plans do not yet include an
`authentication` block**. Wiring it in is a per-target step you add to the plan
today. Two complementary approaches (see [`docs/design.md`](docs/design.md)):

1. **Behind the proxy**: ZAP Browser-Based Authentication can drive the real
   OIDC login headlessly and re-authenticate when the session drops, once you add
   an `authentication` (browser) + `verification` block to the plan. Use a
   dedicated low-privilege scan user.
2. **Origin directly**: scan the in-cluster Service, bypassing the proxy, to
   test the app as if the proxy were removed (defense-in-depth).

## Run it locally

```bash
uv sync
cp targets.example.yaml targets.local.yaml                        # then edit it
uv run dastgate run --all --config targets.local.yaml --dry-run   # plan only, no scan
uv run pytest -q
```

`targets.local.yaml` is gitignored, so your real hosts never get committed.

The container image (`Dockerfile`) bundles ZAP + headless browsers + Nuclei +
the CLI; the actual scanning happens there. See
[`docs/setup.md`](docs/setup.md).

## Status

The orchestration, config model, DefectDojo uploader, ZAP/Nuclei command
building, Helm chart, and container image are **implemented and unit-tested**.
The end-to-end scan path (a real `zap.sh`/`nuclei` run in-cluster) should be
validated against your own environment before you rely on it. Start with a
single `baseline` target against a safe host.

## Documentation

Full docs (MkDocs): `pip install mkdocs-material && mkdocs serve`, or just read
[`docs/`](docs/).

- [Setup](docs/setup.md): local dev, building the image
- [Deployment](docs/deployment.md): Helm on any cluster
- [Configuration](docs/configuration.md): `targets.yaml` + chart values
- [Architecture](docs/architecture.md): module map + data flow
- [Design](docs/design.md): tool choice, DefectDojo semantics, rationale

## Conventions

Python ≥ 3.11, **uv + Ruff + pytest**, full type hints. The core has one runtime
dependency (a YAML parser); the scan engines run as pinned binaries in the image.

## License

MIT. See [`LICENSE`](LICENSE).
