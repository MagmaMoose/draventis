# Design

Why dastgate is shaped the way it is. This is the reasoning behind the code, not
a how-to (see [Deployment](deployment.md) and [Configuration](configuration.md)
for that).

## Headline decisions

- **ZAP is the primary engine, Nuclei the complement.** ZAP (via the Automation
  Framework) is the deep, stateful, authenticated crawler + active scanner.
  Nuclei is the fast, low-false-positive templated layer (known CVEs, exposures,
  misconfig) with optional `-dast` fuzzing. Both are FOSS and — critically —
  **both have first-class DefectDojo parsers** (`ZAP Scan` XML, `Nuclei Scan`
  JSON).
- **DAST runs as a scheduled CronJob**, not in CI on a PR, because DAST needs a
  **running target**. Your cluster already runs your apps; scan those.
- **Baseline into DefectDojo, not diff-gated.** DAST is non-deterministic and has
  no merge-base to diff against, so dastgate does not try to be a PR gate. It
  reimports on a schedule and lets DefectDojo compute drift (see below).
- **Non-destructive by default.** `baseline` (passive) is safe against
  production; `full`/`api` (active) must target staging only.

## What DAST adds over static analysis

Static analysis reasons about source and artifacts at rest. It never sends an
HTTP request to a running instance.

| Class | Why static analysis misses it | DAST catches it |
|---|---|---|
| AuthN/session | Emergent from config + runtime state (cookie flags, fixation, IDOR) | Exercises real auth flows, replays/swaps sessions |
| Injection reachable at runtime | SAST flags *potential* sinks; can't prove exploitability through the deployed stack | Actively fuzzes params → confirmed SQLi/XSS with a payload |
| Response headers / TLS / cookies | Set by ingress + app *at runtime*, not in the repo | Observes the actual `CSP`, `HSTS`, cookie flags, TLS config |
| CORS misconfig | Depends on deployed origin-reflection logic | Sends cross-origin preflights, detects `ACAO: *` + credentials |
| SSRF / OOB | Needs an actual outbound request from the running app | OOB interaction (callback server) proves it |
| Business-logic / API surface | No spec-awareness | Imports OpenAPI, drives operations, finds undocumented endpoints |
| Config drift | Repo ≠ what's actually deployed | Tests the *live* endpoint as an attacker sees it |

## Tool evaluation

| Tool | License | Best at | DefectDojo parser | Verdict |
|---|---|---|---|---|
| **OWASP ZAP** | Apache-2.0 / $0 | Full active scan, auth, OpenAPI/GraphQL/SOAP import, Automation Framework | **`ZAP Scan` (XML)** | **PRIMARY** |
| **Nuclei** | MIT / $0 | Fast known-CVE + exposure + misconfig; templated OOB fuzzing (`-dast`) | **`Nuclei Scan` (JSON)** | **COMPLEMENT** |
| Wapiti | FOSS / $0 | Lightweight black-box param fuzzing | `Wapiti Scan` | Optional third opinion |
| Nikto | FOSS / $0 | Server/CGI misconfig | Generic/CSV only | Low value when a modern ingress fronts everything |
| Schemathesis | FOSS / $0 | Property-based API testing from OpenAPI/GraphQL | Generic / JUnit XML | Adopt as a CI test for spec'd services |
| StackHawk | Commercial | Developer-DX API DAST in CI (ZAP-derived) | `StackHawk HawkScan` | Redundant when ZAP+Nuclei cover it |
| Burp Suite | Commercial | Manual pentest + enterprise DAST | `Burp XML` | Keep as a manual bench tool, not the automation engine |

**Why ZAP + Nuclei (not one, not a commercial tool):** breadth (Nuclei) + depth
(ZAP), two native DefectDojo parsers, zero license spend. Commercial DAST buys DX
you can reproduce with the Automation Framework + your own DefectDojo hub.

### ZAP scan modes

The Automation Framework (a single declarative YAML plan) is the standard for
every dastgate job; it replaced the old `zap-baseline`/`zap-full-scan` shell
entry points. dastgate ships one plan per policy in [`automation/`](https://github.com/MagmaMoose/dastgate/tree/main/automation):

| Plan | Jobs | dastgate policy |
|---|---|---|
| `zap-baseline.yaml` | spider + passive | `baseline` — nightly, prod-safe |
| `full-active.yaml` | + ajax-spider + active | `full` — weekly, staging only |
| `api-scan.yaml` | OpenAPI import → spider → active | `api` — services with a spec |

## DefectDojo ingestion

dastgate POSTs each report to **`POST /api/v2/reimport-scan/`** (multipart form)
with:

- `scan_type` = `"ZAP Scan"` / `"Nuclei Scan"`
- `product_name` + `engagement_name` + `auto_create_context=true`
  → DefectDojo auto-creates the product/engagement/test on first run (no
  pre-provisioning).
- `test_title` — a stable dedupe key across runs.
- `close_old_findings=true` → fixed alerts auto-mitigate per engagement.
- `tags`, optional `product_type_name`.

### Why reimport, not import

Reimport compares the incoming report to the existing test and **won't create
duplicates**; it reactivates regressions and, with `close_old_findings`,
mitigates alerts that disappeared. That yields "what's new / fixed since last
scan" *for free* — the drift signal DAST needs — without a merge-base diff.

### Engagement/test modeling

```
Product:     example/app
  Engagement: "DAST - app-staging"   (auto-created)
    Test:     "ZAP Scan"             ← reimport nightly/weekly
    Test:     "Nuclei Scan"          ← reimport nightly
```

DefectDojo stays the durable triage system of record: mark false positives /
risk-accept there once, and reimport dedupe preserves that state across runs.

## Where DAST runs

DAST needs a running target. The default placement is a **scheduled CronJob
against already-deployed environments** — the cluster already runs everything, it
fits a secrets-from-a-store idiom, and it decouples slow/destructive active scans
from PR latency.

- **Nightly** — ZAP baseline (passive) on prod-facing + staging hosts, plus
  Nuclei templated/known-CVE (non-destructive).
- **Weekly** — ZAP full active + Nuclei `-dast` fuzzing against **staging only**.

An **optional per-PR ephemeral-env scan** (spin the app up in CI, scan, gate) is
worth it only when a service ships an OpenAPI spec and you want API-contract DAST
on every change, or you already build preview environments. For most repos the
scheduled staging scan catches the same classes a day later at a fraction of the
cost.

## Authenticated scanning

Most apps behind an OIDC proxy need dastgate to authenticate. Do both:

1. **Scan behind the proxy** (app-layer bugs) — ZAP Browser-Based Authentication
   drives the real OIDC login in a headless browser and uses a poll-based
   verification strategy to re-authenticate when the session drops. Give your
   identity provider a dedicated low-privilege scan user.
2. **Scan the origin directly** (the app's own attack surface) — in-cluster, hit
   the Service directly, bypassing the proxy. This tests the app as if the proxy
   were removed — valuable, since a misconfigured route would strip your only
   authn layer.

**Safety:** targets and credentials come **only** from config you control, never
from a scanned response. Active scans hit staging, never production.

## Net-new philosophy — baseline, not diff-gated

DAST is baseline-only, deliberately **not** a merge-base diff gate:

- **No merge-base to diff against** — DAST runs against a deployed environment,
  not a PR's changed lines. There is no `git diff` for "this response header
  regressed."
- **DAST is non-deterministic** — crawler coverage, timing, and active-scan
  payload success vary run to run; a naive "new since last run" gate would flap.
- **DefectDojo already gives the safe version of net-new** — reimport dedupe +
  `close_old_findings` yields reactivated (regressed) and new finding states
  without a merge-base. Pair that with SLA tracking so new Highs get a clock.

The one place a gate belongs is the optional per-PR ephemeral packaging, and even
there gate on **ZAP's own new-alert delta** vs a committed baseline, not a SARIF
merge-base diff.

## Container & hardening

The image builds on the official ZAP image (ZAP + JRE + headless browsers for
browser-based auth) plus the Nuclei binary and the `dastgate` package. It runs
**non-root** with `seccompProfile: RuntimeDefault` and all capabilities dropped;
only `/zap/wrk` (an `emptyDir`) is writable. dastgate needs **no Kubernetes API
access** — it only makes HTTP requests to targets and DefectDojo — so its
ServiceAccount has no RBAC and does not mount a token: a deliberately minimal
blast radius.

## Rollout (crawl / walk / run)

A safe way to adopt dastgate incrementally:

- **Crawl** — one nightly `baseline` target against a safe host; prove the ZAP
  reimport pipe lands in DefectDojo with `auto_create_context`.
- **Walk** — enable Nuclei; wire browser-based OIDC auth for one staging app; add
  the weekly full-active CronJob against staging only.
- **Run** — expand `targets.yaml` to all apps (passive prod / active staging);
  add `openapi` + Nuclei `-dast` API scanning and Schemathesis for spec'd
  services.
