# dastgate

Scheduled **DAST** (Dynamic Application Security Testing) for MagmaMoose:
**OWASP ZAP by Checkmarx** (driven by the ZAP Automation Framework) +
**Nuclei** run on a schedule against deployed/staging environments, with
results reimported into **DefectDojo**.

> **Status: Phase 1 — nightly ZAP baseline.** The `src/dastgate` package renders +
> runs a ZAP Automation Framework **baseline** (passive) plan per target and
> reimports the report into DefectDojo (`ZAP Scan` parser). Ships as a Helm chart
> (a nightly CronJob + ExternalSecret) — see [Running](#running-phase-1). Not yet
> wired into Flux. Nuclei, authenticated, and full-active scans are later phases;
> see [`docs/DESIGN.md`](docs/DESIGN.md) and its crawl/walk/run rollout.

---

## Running (Phase 1)

Cluster (Helm — a nightly CronJob + ExternalSecret; targets + DefectDojo token come
from OCI Vault via External Secrets Operator):

```sh
helm template dastgate charts/dastgate      # render/inspect
```

Container (ZAP + the `dastgate` CLI baked in):

```sh
docker build -t ghcr.io/magmamoose/dastgate:0.1.0 .
docker run --rm -v "$PWD/targets.yaml:/etc/dastgate/targets.yaml:ro" \
  -e DEFECTDOJO_URL -e DEFECTDOJO_TOKEN \
  ghcr.io/magmamoose/dastgate:0.1.0 run --all
```

Locally, scan-only (no upload — needs `zap.sh` on `PATH`):

```sh
uv run dastgate run --all --no-upload --targets-file targets.yaml --automation-dir automation
```

`targets.yaml` (also the OCI-Vault `dastgate-targets` key):

```yaml
targets:
  - name: my-service            # DefectDojo product
    url: https://my-service.magmamoose.com
    plan: zap-baseline          # optional (automation/<plan>.yaml)
    engagement: DAST            # optional
```

DefectDojo config comes from the environment (`DEFECTDOJO_URL`, `DEFECTDOJO_TOKEN`,
`DD_PRODUCT_TYPE`). The uploader is **failure-isolated** — a DefectDojo outage is
logged and never fails the scan job.

---

## What DAST adds

The existing MagmaMoose stack ([chargate](https://github.com/MagmaMoose/chargate)
wrapping MegaLinter: Trivy, Grype, OSV-Scanner, Semgrep, Checkov, KICS, gitleaks,
kubeconform) reasons about **source and artifacts at rest**. It never sends a
single HTTP request to a running instance. DAST closes the "does the deployed
thing actually behave insecurely?" gap — authn/session handling, injection that
is only reachable at runtime, response-header/TLS/cookie posture, CORS
misconfiguration, SSRF, live API surface, and config drift between the repo and
what Flux actually deployed.

For MagmaMoose specifically, every app is exposed through **Cloudflare Tunnel →
oauth2-proxy/authentik → app**. That chain is exactly where header, CORS, and
session bugs live — and only a running-target scanner can see the truth there.

## Tool decision

- **ZAP by Checkmarx** (formerly OWASP ZAP) is the **primary** engine — the deep,
  stateful, authenticated crawler + active scanner — driven by the **Automation
  Framework** (a single declarative YAML plan that replaced the old
  `zap-baseline` / `zap-full-scan` shell entry points).
- **Nuclei** is the **complementary** fast, low-false-positive templated layer:
  known CVEs, exposed `.git`/actuators/dashboards, default creds, plus `-dast`
  fuzzing that can be seeded from the same OpenAPI spec.
- Both are actively maintained in 2026, both are FOSS ($0), and — critically —
  **both have first-class native DefectDojo parsers** (`ZAP Scan` XML,
  `Nuclei Scan` JSON). Commercial DAST (StackHawk / Burp Enterprise / Detectify /
  Probely) is deliberately shelved; see the design doc for the full evaluation.

## Architecture stance

dastgate is **not** chargate. Read this before assuming it behaves like the
PR-time gate:

- **Runs as a scheduled Kubernetes CronJob**, not in CI on a PR. DAST needs a
  **running target**; the GitOps cluster already runs every app, so scans hit the
  already-deployed `*.staging.magmamoose.com` (active) and `*.magmamoose.com`
  (passive-only) hosts.
- **Baseline-only into DefectDojo — NOT merge-base diff-gated like chargate.**
  There is no `git diff` semantic for "this response header regressed," and DAST
  is non-deterministic (crawler coverage/timing/payload success vary run to run),
  so a naive net-new gate would flap. Instead DefectDojo's `reimport-scan` dedupe
  + `close_old_findings` gives the *safe* version of "what's new / fixed since
  last scan," paired with SLA tracking. dastgate keeps chargate's net-new gate as
  a strictly **SAST/SCA** concept and does not overload it onto DAST.
- **Non-destructive by default.** Passive-only baseline on prod hosts; active
  scans and `-dast` fuzzing hit **staging only**.

## Authenticated scanning

Most `*.magmamoose.com` apps sit behind **oauth2-proxy + authentik (OIDC)**, so
useful DAST has to authenticate. The plan is to do **both**: (1) scan *behind* the
proxy using ZAP **Browser-Based Authentication** in the Automation Framework
(drive the real OIDC login headlessly, poll a known authenticated URL to
re-auth on session drop) with a dedicated low-privilege `scanbot` authentik user,
and (2) scan the **origin Service directly** in-cluster to test the app as if the
proxy were removed (defense-in-depth). Scan credentials come **only** from OCI
Vault config we control — never from a scanned response.

## Rollout (crawl / walk / run)

- **Crawl** — passive ZAP baseline against one safe target
  (`defectdojo.magmamoose.com`), prove the `ZAP Scan` reimport pipe, ship the repo
  scaffold + Helm chart + one nightly CronJob. No active scanning, no auth yet.
- **Walk** — add Nuclei nightly, wire browser-based OIDC auth for one staging app,
  add the weekly full-active CronJob against staging only, reuse the GitHub-issue
  auto-push for new High/Crit findings.
- **Run** — expand `targets.yaml` to all apps (passive prod / active staging), add
  `openapi` + Nuclei `-dast` API scanning and Schemathesis for services with
  specs, publish the opt-in reusable per-PR DAST workflow.

Full detail: [`docs/DESIGN.md`](docs/DESIGN.md).

## How this fits the MagmaMoose security program

- **[MagmaMoose/chargate](https://github.com/MagmaMoose/chargate)** — the
  **PR-time** SAST/SCA/IaC/secrets gate (MegaLinter + net-new diff gating). Static
  analysis at rest. dastgate is the runtime complement; they share the DefectDojo
  uploader ethos (stdlib `urllib`, failure-isolated) but nothing else.
- **[MagmaMoose/securitybridge](https://github.com/MagmaMoose/securitybridge)** —
  the long-lived Dependency-Track ↔ DefectDojo sync backend (the "finding bus").
  dastgate lands its findings in the same DefectDojo hub that securitybridge feeds.
- **[MagmaMoose/security-platform](https://github.com/MagmaMoose/security-platform)**
  — the program index and security-tooling roadmap that ties chargate,
  securitybridge, and dastgate together.
- **DefectDojo** (self-hosted, in the private infra repo) — the durable triage
  system of record and the sink every source reports into. **Dependency-Track**
  (also self-hosted) is the SBOM/component hub feeding securitybridge.

## Conventions

Mirrors the [chargate](https://github.com/MagmaMoose/chargate) sibling: Python
≥ 3.11, **uv + Ruff + pytest**, full type hints. External GitHub Actions are
SHA-pinned with a `# vX.Y.Z` comment. Deployed to the **k3s** cluster via
**FluxCD** with **External Secrets Operator** (OCI Vault) + **cloudflared**
tunnel. MIT licensed.
