# dastgate — Design

**Status:** Accepted design · Phase 0 (Planning) · **Date:** 2026-07-22

Runtime (DAST) coverage for MagmaMoose as a *separate, modular* project deployed
via the existing Flux / ESO / cloudflared pattern — **not** bolted into
[chargate](https://github.com/MagmaMoose/chargate) (which stays scoped to CI/PR-time
static analysis). Findings land in the same self-hosted DefectDojo hub that
[securitybridge](https://github.com/MagmaMoose/securitybridge) feeds, and the
project sits alongside chargate and securitybridge under the
[security-platform](https://github.com/MagmaMoose/security-platform) roadmap.

---

## TL;DR / headline decisions

- **ZAP by Checkmarx (formerly OWASP ZAP) is the primary DAST engine**, driven by
  the **Automation Framework** (single YAML plan), with **Nuclei (`-dast` +
  templated CVE/exposure checks) as a fast complementary scanner**. Both are
  actively maintained in 2026 and — critically — **both have first-class
  DefectDojo parsers** (`ZAP Scan` XML, `Nuclei Scan` JSON).
- **DAST runs as a scheduled Kubernetes CronJob** ("dastgate") against the
  already-deployed `*.magmamoose.com` / `*.staging.magmamoose.com` targets —
  mirroring the existing `dt-defectdojo-sync` pattern (config in OCI Vault,
  results POSTed to DefectDojo `reimport-scan`). This is the correct baseline
  because **DAST needs a running target**, and the GitOps cluster already runs
  everything.
- **DAST is *not* diff-gated like chargate.** It is **baseline-only** into
  DefectDojo (dedupe + `close_old_findings` for drift + SLA tracking). A
  chargate-style net-new gate only makes sense in the optional per-PR
  ephemeral-env packaging, and even there it should gate on ZAP's *own* new-alert
  delta, not a merge-base diff.
- **Commercial DAST (StackHawk/Burp Enterprise/Detectify/Probely) is out of
  scope for now** — a solo operator doesn't need per-seat DAST when ZAP+Nuclei
  cover the surface and land natively in DefectDojo. StackHawk stays on the "if
  API DAST DX becomes painful" shelf (it *is* ZAP-derived and has a native
  `StackHawk HawkScan` parser).

---

## 1. What DAST adds that SAST/SCA/IaC/secrets do not

The current stack (MegaLinter + [chargate](https://github.com/MagmaMoose/chargate):
Trivy, Grype, OSV-Scanner, Semgrep, Checkov, KICS, gitleaks, kubeconform) reasons
about **source and artifacts at rest**. It never sends a single HTTP request to a
running instance. DAST closes the "does the deployed thing actually behave
insecurely?" gap:

| Class | Why static analysis misses it | DAST catches it |
|---|---|---|
| **AuthN/session** | Login/session logic is emergent from config + runtime state (cookie flags, session fixation, JWT accepted unsigned, IDOR across users) | Exercises real auth flows, replays sessions, swaps user tokens |
| **Injection reachable at runtime** | SAST flags *potential* sinks; can't prove exploitability through the deployed WAF/ORM/framework | Actively fuzzes params → confirmed SQLi/XSS/command-injection with a working payload |
| **Response headers / TLS / cookies** | Headers are set by ingress (cloudflared, oauth2-proxy) + app *at runtime*, not in repo | Observes actual `CSP`, `HSTS`, `X-Frame-Options`, cookie `Secure`/`HttpOnly`/`SameSite`, TLS config |
| **CORS misconfig** | Depends on deployed origin-reflection logic | Sends cross-origin preflights, detects `ACAO: *` + credentials |
| **SSRF / OOB** | Needs an actual outbound request from the running app | ZAP/Nuclei OOB interaction (callback server) proves it |
| **Business-logic / API surface** | No spec-awareness; can't enumerate live endpoints | Imports OpenAPI/GraphQL/SOAP, drives every operation, finds undocumented/exposed endpoints |
| **Config drift between repo and prod** | Repo ≠ what's actually deployed via Flux + Helm values | Tests the *live* endpoint as an attacker sees it |

For MagmaMoose specifically: everything is exposed through **Cloudflare Tunnel →
oauth2-proxy/authentik → app**. That chain is exactly where header/CORS/session
bugs live and where only a running-target scanner can see the truth.

---

## 2. Tool evaluation

All maintenance/format facts below were verified against 2026 sources (linked).

| Tool | 2026 status | License / cost | Best at | DefectDojo parser | Verdict |
|---|---|---|---|---|---|
| **ZAP by Checkmarx** (ex-OWASP ZAP) | **Actively maintained**; Checkmarx hired all 3 leads (Sep 2024), weekly + stable releases, still Apache-2.0 FOSS ([1](https://www.zaproxy.org/docs/team/psiinon/), [2](https://markets.financialcontent.com/wss/article/bizwire-2024-9-24-checkmarx-joins-forces-with-zap-to-supercharge-dynamic-application-security-testing-dast-for-the-enterprise-and-enhance-community-growth)) | FOSS / $0 | Full active scan, auth, OpenAPI/GraphQL/SOAP import, Automation Framework | **Yes — `ZAP Scan` (XML)** ([docs](https://docs.defectdojo.com/supported_tools/parsers/)) | **PRIMARY** |
| **Nuclei** (ProjectDiscovery) | **Very active**; v3.2+ added DAST/fuzzing (`-dast`), OpenAPI/Swagger request generation, authenticated scanning, 12k+ templates ([3](https://github.com/projectdiscovery/nuclei), [4](https://projectdiscovery.io/blog/nuclei-fuzzing-for-unknown-vulnerabilities)) | FOSS / $0 | Fast known-CVE + exposure + misconfig checks; templated OOB fuzzing | **Yes — `Nuclei Scan` (JSON)** ([docs](https://docs.defectdojo.com/en/connecting_your_tools/parsers/file/nuclei/)) | **COMPLEMENT** |
| **Wapiti** | **Maintained** (v3.3.0, May 2026) ([5](https://wapiti-scanner.github.io/)) | FOSS / $0 | Lightweight black-box param fuzzing | **Yes — `Wapiti Scan`** | Optional 3rd opinion; not needed if ZAP+Nuclei run |
| **Nikto** | **Maintained** (v2.6.0, Feb 2026) ([6](https://en.wikipedia.org/wiki/Nikto_(vulnerability_scanner))) | FOSS / $0 | Server/CGI misconfig, dated files | No dedicated parser → **generic/CSV** | Low value here (cloudflared fronts everything); skip |
| **Arachni** | **DEAD** — archived ~2020 ([7](https://geekflare.com/cybersecurity/open-source-web-security-scanner/)) | — | — | (legacy parser exists) | **Do not use** |
| **w3af** | **Effectively dead** — Python 2.7, unmaintained ([7](https://geekflare.com/cybersecurity/open-source-web-security-scanner/)) | — | — | No | **Do not use** |
| **StackHawk** | Active, ZAP-derived, CI-first, `stackhawk.yml` in VCS; REST/GraphQL/SOAP/gRPC + HawkAI endpoint discovery ([8](https://appsecsanta.com/stackhawk)) | **Commercial** ~$39/contributor/mo ([9](https://beaglesecurity.com/blog/article/stackhawk-pricing.html)) | Developer-DX API DAST in CI | **Yes — `StackHawk HawkScan`** | Nice, but redundant for a solo op; shelf it |
| **Burp Suite** (Pro/DAST/Enterprise) | Active, best-in-class manual+scanner | **Commercial** (Pro ~$0.5k/yr; Enterprise $$$$) ([10](https://pentest.ae/dast-tools-comparison-2026/)) | Manual pentest + enterprise DAST | **Yes — `Burp XML` / `Burp Suite DAST Scan`** | Keep Burp *Community/Pro* as a manual bench tool, not the automation engine |
| **Detectify / Probely** | Active SaaS DAST | Commercial SaaS | Zero-ops managed scanning | Probely: generic; varies | Overkill/cost for solo op; skip |
| **Schemathesis** | **Very active**; property-based API testing from OpenAPI/GraphQL, finds spec violations/500s, JUnit XML out ([11](https://schemathesis.io/), [12](https://github.com/schemathesis/schemathesis)) | FOSS / $0 | API-spec fuzzing / contract-breaking | No dedicated parser → **generic / JUnit XML** | **Adopt for any OpenAPI service** as a CI test (complements DAST, not a replacement) |

### Why ZAP + Nuclei (not one, not StackHawk)

- **ZAP** is the deep, stateful, authenticated crawler+active-scanner. The
  Automation Framework replaced the old `zap-baseline`/`zap-full-scan` shell
  entry points with one declarative YAML plan and is now the recommended path
  for any non-trivial scan ([AF docs](https://www.zaproxy.org/docs/automate/automation-framework/)).
- **Nuclei** is the fast, low-false-positive templated layer: known CVEs,
  exposed `.git`/actuators/dashboards, default creds, plus `-dast` fuzzing that
  can be **seeded from the same OpenAPI spec** ([Nuclei Swagger](https://github.com/orgs/projectdiscovery/discussions/4987)).
  Running both gives breadth (Nuclei) + depth (ZAP) with **two native
  DefectDojo parsers** and zero license spend.
- **StackHawk is ZAP under the hood** ([13](https://www.stackhawk.com/blog/guide-to-zap-application-security-testing/));
  paying per-contributor buys DX we can reproduce with the Automation Framework
  + our existing DefectDojo hub. Revisit only if authenticated API scan config
  becomes a time sink.

### ZAP scan-mode cheat-sheet

| Mode | What it does | Use in dastgate |
|---|---|---|
| `zap-baseline` (passive) | Spider + **passive** only, no attacks; safe, fast, non-destructive | **Nightly** on prod-facing hosts (safe against real prod) |
| `zap-full-scan` (active) | Spider + ajax-spider + **active** attacks | **Weekly** against **staging only** |
| `zap-api-scan` | Import OpenAPI/GraphQL/SOAP, scan API operations | Per-service where a spec exists |
| **Automation Framework** | One YAML plan orchestrating all of the above + auth + reports | **Standard for all dastgate jobs** |

---

## 3. DefectDojo ingestion

**Parsers exist and are current** — verified against the DefectDojo supported-tools
list ([parsers index](https://docs.defectdojo.com/supported_tools/parsers/)):

- **ZAP** → parser page "Zed Attack Proxy"; **API `scan_type: "ZAP Scan"`**;
  ingests ZAP's **traditional XML** report ([14](https://docs.defectdojo.com/supported_tools/parsers/)).
- **Nuclei** → **`scan_type: "Nuclei Scan"`**, ingests Nuclei **JSON**
  (`-jsonl`/`-json-export`) ([Nuclei parser](https://docs.defectdojo.com/en/connecting_your_tools/parsers/file/nuclei/)).
- Fallbacks: **`Generic Findings Import`** (JSON/CSV) for Schemathesis/Nikto/
  anything without a native parser.

### Reimport vs import (idempotency)

Use **`POST /api/v2/reimport-scan/`** — exactly what `dt-defectdojo-sync`
already does. Reimport compares the incoming report to the existing test and
**won't create duplicates**; it reactivates regressions and (with
`close_old_findings=true`) mitigates alerts that disappeared — i.e. it gives you
"what's new / fixed since last scan" *for free*, which is the drift signal DAST
needs ([reimport semantics](https://docs.defectdojo.com/asset_modelling/engagements_tests/os__tests/)).

### Engagement/test modeling for DAST

Mirror the DT-sync convention — **one product per app, one long-lived
CI/CD-type engagement per DAST target**, one test per scanner:

```
Product:     magmamoose/app
  Engagement: "DAST — app.staging" (type: CI/CD, recurring)
    Test:     "ZAP Scan"      ← reimport nightly/weekly
    Test:     "Nuclei Scan"   ← reimport nightly
```

Key `reimport-scan` fields (multipart form), same knobs as the DT sync:

- `scan_type` = `"ZAP Scan"` / `"Nuclei Scan"`
- `product_name` + `engagement_name` + `auto_create_context=true`
  → DefectDojo auto-creates the product/engagement/test on first run (no
  pre-provisioning), exactly like the DT→DD job.
- `test_title` to pin the test (stable dedupe key across runs).
- `close_old_findings=true`, `close_old_findings_product_scope=false`
  → fixed alerts auto-mitigate per engagement.
- `tags=dast,zap,staging`, `build_id`/`commit_hash` for traceability.

---

## 4. Where DAST runs — the key architectural question

DAST needs a **running target**. Three placements, with a recommendation:

### Option A — Scheduled CronJob against deployed/staging envs  ✅ RECOMMENDED baseline

A `security`-namespace CronJob (same shape as `dt-defectdojo-sync`) hits the
already-running `*.staging.magmamoose.com` (active) and `*.magmamoose.com`
(passive-only) targets and reimports into DefectDojo.

**Why it's the right default here:**
- The GitOps cluster already runs every app — no environment to spin up.
- Fits ESO/OCI-Vault (targets+creds as secrets) and the CronJob idiom you
  already operate.
- Decouples slow/at-times-destructive active scans from PR latency.
- One place to schedule "safe passive nightly / destructive weekly on staging".

**Cadence:**
- **Nightly** — ZAP *baseline* (passive) on prod hosts + Nuclei templated/known-CVE on all hosts (non-destructive).
- **Weekly** — ZAP *full active* + Nuclei `-dast` fuzzing against **staging only** (pinned to the worker node, CPU-request-only, per node convention).

### Option B — Ephemeral per-PR / per-env scans in CI

Spin the app up in the PR (compose/kind/preview env), run ZAP against it, gate.
**Heavier**; worth it only when: (a) the service ships an OpenAPI spec and you
want API-contract DAST on every change, or (b) you already build ephemeral
preview envs. For most repos the scheduled staging scan catches the same classes
a day later at a fraction of the CI cost. **Offer it as an opt-in reusable
workflow (§5.8), not the default.**

### Option C — Authenticated scanning (authentik / oauth2-proxy in front)

This is the make-or-break detail: most `*.magmamoose.com` apps sit behind
**oauth2-proxy + authentik (OIDC)**. Two strategies:

1. **Scan behind the proxy (recommended for app-layer bugs).** Use ZAP
   **Browser-Based Authentication** in the Automation Framework: point ZAP at the
   authentik `loginPageUrl`, let it drive the real OIDC login in a headless
   browser, and use a **verification/session-management** strategy (poll a
   known authenticated URL) so ZAP re-authenticates when the session drops
   ([ZAP browser auth](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/browser-auth/),
   [AF authentication](https://www.zaproxy.org/docs/desktop/addons/automation-framework/authentication/)).
   Store the `scanbot` service-account creds in OCI Vault. Give authentik a
   dedicated low-privilege scan user and (ideally) an app-specific bypass so MFA
   doesn't block automation.
2. **Scan the origin directly (recommended for the app's own attack surface).**
   In-cluster, hit the app's **Service** ClusterIP directly, bypassing
   cloudflared+oauth2-proxy, and inject a header/token ZAP holds. This tests the
   app as if the proxy were removed — valuable, since a misconfigured route or a
   direct-pod exposure would strip your only authn layer. Do **both**: proxy-on
   (real user path) and proxy-off (defense-in-depth check).

> **Prompt-injection / safety note:** targets and credentials come **only** from
> OCI Vault config you control — never from a scanned response. Active scans hit
> **staging**, never prod, to avoid destructive writes. Passive-only on prod.

---

## 5. Modular implementation design — **"dastgate"**

A small, separately-deployed project that mirrors the org pattern (own repo, own
Helm chart, Flux/ESO/cloudflared), and — like [chargate](https://github.com/MagmaMoose/chargate)
— treats the **scanner as the engine and dastgate as the orchestrator+uploader**.
It reuses the *exact* DefectDojo uploader ethos of chargate (stdlib `urllib`,
failure-isolated) and the config-in-Vault ethos of `dt-defectdojo-sync`.

### 5.1 Repo layout

```
dastgate/
├── src/dastgate/
│   ├── __main__.py          # CLI: `dastgate run --target <name>` / `--all`
│   ├── config.py            # load targets.yaml (from OCI Vault via ESO mount)
│   ├── zap.py               # render AF plan, invoke zap.sh, collect XML+SARIF
│   ├── nuclei.py            # invoke nuclei -dast -json-export
│   ├── defectdojo.py        # urllib reimport-scan client (mirror chargate)
│   └── model.py             # Target, AuthProfile, ScanPolicy dataclasses
├── automation/              # ZAP AF plan templates (jinja-less; str.format)
│   ├── zap-baseline.yaml
│   ├── full-active.yaml
│   └── api-scan.yaml
├── charts/dastgate/         # Helm chart (CronJobs, RBAC, ExternalSecret)
├── Dockerfile               # FROM ghcr.io/zaproxy/zaproxy:stable + nuclei + py
├── .github/workflows/       # reusable workflow for per-PR opt-in (§5.8)
└── tests/                   # mirror modules 1:1 (uploader is unit-tested w/ fakes)
```

> **Phase 0 note:** today the repo has `automation/`, `charts/dastgate/` (stub),
> this doc, and an **empty** `src/dastgate/` package (version `0.0.0`, with a
> `pyproject.toml` + console-script stub). The modules listed above describe the
> intended shape, not shipped code.

### 5.2 Container

`FROM zaproxy/zaproxy:stable` (ships ZAP + JRE + browsers for browser-auth),
`+ nuclei` binary, `+ python3` and the `dastgate` package. Non-root, seccomp
`RuntimeDefault`, `readOnlyRootFilesystem: false` only for `/zap/wrk` (scan
workdir) — everything else read-only, matching pod conventions. Pin the
heavy full-active CronJob to the worker node; **CPU requests only, no limits**.

### 5.3 Config model (targets list in OCI Vault, per-target auth + policy)

A single OCI-Vault key `dastgate-targets` (fetched by ESO into a Secret, mounted
as `targets.yaml`) — analogous to the single Vault key the DT-sync uses for
GitHub owners:

```yaml
# targets.yaml  (source of truth in OCI Vault)
defaults:
  defectdojo:
    product_field: name           # DTrack/DD product name = target.product
    engagement_prefix: "DAST — "
  policy: baseline                 # baseline|full|api
targets:
  - name: app-staging
    product: magmamoose/app
    url: https://app.staging.magmamoose.com
    policy: full                   # active scan allowed (staging)
    openapi: https://app.staging.magmamoose.com/openapi.json
    auth:
      type: browser-oidc           # authentik/oauth2-proxy
      login_url: https://app.staging.magmamoose.com/login
      user_ref: dastgate-app-staging-user   # → ESO secret keys
    schedule: weekly
  - name: app-prod
    product: magmamoose/app
    url: https://app.magmamoose.com
    policy: baseline               # passive only on prod
    schedule: nightly
  - name: dojo
    product: magmamoose/defectdojo
    url: https://defectdojo.magmamoose.com
    policy: baseline
    schedule: nightly
```

### 5.4 Concrete ZAP Automation Framework plan (authenticated API scan)

Rendered by `zap.py` per target. Job types (`openapi`, `spider`, `spiderAjax`,
`activeScan`, `passiveScan-*`, `report`, `alertFilter`) are the current AF set
([AF docs](https://www.zaproxy.org/docs/automate/automation-framework/)):

```yaml
env:
  contexts:
    - name: app-staging
      urls: [ "https://app.staging.magmamoose.com" ]
      includePaths: [ "https://app.staging.magmamoose.com/.*" ]
      excludePaths: [ ".*/logout.*", ".*/admin/delete.*" ]   # avoid destructive
      authentication:
        method: browser
        parameters:
          loginPageUrl: "https://app.staging.magmamoose.com/login"
          browserId: firefox-headless
      sessionManagement: { method: headers }
      verification:
        method: poll
        pollUrl: "https://app.staging.magmamoose.com/api/me"
        pollAdditionalHeaders: []
      users:
        - name: scanbot
          credentials: { username: "${ZAP_USER}", password: "${ZAP_PASS}" }
  parameters: { failOnError: true, progressToStdout: true }

jobs:
  - type: openapi                      # import the spec → seed the site tree
    parameters: { apiUrl: "https://app.staging.magmamoose.com/openapi.json",
                  targetUrl: "https://app.staging.magmamoose.com", context: app-staging }
  - type: passiveScan-config
    parameters: { enableTags: false }
  - type: spider
    parameters: { context: app-staging, user: scanbot, maxDuration: 5 }
  - type: spiderAjax
    parameters: { context: app-staging, user: scanbot, maxDuration: 5 }
  - type: passiveScan-wait
  - type: activeScan                    # ONLY on staging targets
    parameters: { context: app-staging, user: scanbot, policy: "API-minimal" }
  - type: alertFilter                   # false-positive suppression (see §5.7)
    parameters:
      alertFilters:
        - { ruleId: 10096, newRisk: "False Positive" }   # e.g. timestamp disclosure
  - type: report                        # DefectDojo-ingestible XML
    parameters: { template: "traditional-xml", reportDir: "/zap/wrk", reportFile: "zap.xml" }
```

Baseline plan = the same minus `spiderAjax` + `activeScan` (passive only). See
[`automation/zap-baseline.yaml`](../automation/zap-baseline.yaml) for the
committed example skeleton.

### 5.5 DefectDojo upload (sketch — mirror chargate's urllib uploader)

```python
# defectdojo.py — stdlib only, failure-isolated (never fail the scan on upload err)
import urllib.request, mimetypes, uuid, os

def reimport(base_url, token, scan_type, report_path, product, engagement, title, tags):
    boundary = uuid.uuid4().hex
    fields = {
        "scan_type": scan_type,                 # "ZAP Scan" | "Nuclei Scan"
        "product_name": product,
        "engagement_name": engagement,          # "DAST — app.staging"
        "test_title": title,
        "auto_create_context": "true",          # same as dt-defectdojo-sync
        "close_old_findings": "true",
        "active": "true", "verified": "false",
        "tags": ",".join(tags),
    }
    body = _multipart(boundary, fields, report_path)   # build multipart/form-data
    req = urllib.request.Request(
        f"{base_url}/api/v2/reimport-scan/", data=body, method="POST",
        headers={"Authorization": f"Token {token}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status                      # 201 created / 200 reimported
    except Exception as e:                        # isolate: log + continue
        print(f"[dastgate] DefectDojo upload failed (non-fatal): {e}")
        return None
```

`DEFECTDOJO_URL` presence enables the sink — same "sink enabled by host-URL
presence" rule chargate uses. Nuclei uploads the same way with
`scan_type="Nuclei Scan"` and its JSON report.

> This is a **design sketch**, not shipped code. `src/dastgate/defectdojo.py`
> does not exist in Phase 0.

### 5.6 Scheduling (Helm → Flux)

Two CronJobs (nightly baseline, weekly full), `concurrencyPolicy: Forbid`,
`activeDeadlineSeconds` caps, results written to an `emptyDir` workdir. RBAC:
dastgate needs **no cluster API access** (it talks HTTP to targets + DefectDojo),
so it runs with a minimal ServiceAccount — a nice blast-radius win vs. the
DT-sync which runs inside the Django image.

```yaml
# charts/dastgate/templates/cronjob-nightly.yaml (excerpt — planned)
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      activeDeadlineSeconds: 5400
      template:
        spec:
          nodeSelector: { role: worker }        # heavy pods → worker (node convention)
          securityContext: { runAsNonRoot: true, seccompProfile: { type: RuntimeDefault } }
          containers:
            - name: dastgate
              args: ["run", "--schedule", "nightly"]
              envFrom: [ { secretRef: { name: dastgate-secrets } } ]  # ESO→OCI Vault
```

### 5.7 Scan-policy & false-positive strategy

- **ZAP `alertFilter` job** for engine-level FP suppression, committed in the
  plan (versioned, reviewable) — e.g. mute a known-benign informational rule.
- **DefectDojo is the durable triage system of record**: mark FPs / risk-accept
  there; reimport dedupe preserves that state across runs (don't re-triage
  nightly). This matches how DT/Sonar findings are already triaged in DefectDojo.
- **Two-tier severity gate:** nightly passive is *report-only* (no alerts fail
  anything); the weekly active run pushes High/Crit into the **same GitHub
  issue auto-push** the DT-sync already does (§6) — reuse that code path so DAST
  Highs get a repo issue like DT Highs do.

### 5.8 Alternative packaging — reusable GitHub workflow (per-repo opt-in)

For repos that *do* build an ephemeral env (Option B), ship a **reusable
workflow** `MagmaMoose/dastgate/.github/workflows/dast.yml` that a repo opts into:

```yaml
# consumer repo: .github/workflows/security-dast.yml
jobs:
  dast:
    uses: MagmaMoose/dastgate/.github/workflows/dast.yml@v1
    with:
      target-url: http://localhost:8080
      openapi: ./openapi.json
      policy: full
    secrets:
      defectdojo-token: ${{ secrets.DEFECTDOJO_TOKEN }}
```

Under the hood it uses **`zaproxy/action-full-scan`** / **`action-api-scan`** (or
the newer Automation Framework Scan action, SHA-pinned with a `# vX.Y.Z` comment
per convention) and then the same `dastgate` uploader ([ZAP actions](https://github.com/zaproxy/action-full-scan)).
This gives per-PR DAST *without* forcing it on every repo — the same "one engine,
two surfaces" philosophy as chargate (action + hook).

---

## 6. Net-new philosophy for DAST — baseline, not diff-gated

**DAST is baseline-only (like the DT→DD sync), NOT chargate-style merge-base
diff-gated.** Rationale:

- **No merge-base to diff against.** DAST runs against a *deployed environment*,
  not a PR's changed lines. There is no `git diff` semantic for "this HTTP
  response header regressed."
- **DAST is non-deterministic.** Crawler coverage, timing, and active-scan
  payload success vary run-to-run; a naive "new since last run" gate would
  flap. Chargate's net-new gate works precisely *because* SARIF+diff is
  deterministic — DAST isn't.
- **DefectDojo already gives you the safe version of "net-new."** Reimport
  dedupe + `close_old_findings` yields *reactivated* (regressed) and *new*
  finding states without a merge-base. Pair that with **SLA tracking** so new
  Highs get a clock, and with the existing **GitHub-issue auto-push** so new
  High/Crit DAST findings open a repo issue — that's the actionable "net-new"
  signal, decoupled from the PR gate.
- **The one place a gate belongs** is the optional per-PR ephemeral packaging
  (§5.8), and even there gate on **ZAP's own new-alert delta vs a committed
  `.zap/` baseline** (ZAP maintains this natively), not a SARIF merge-base diff.

So: **scheduled scans → baseline into DefectDojo (no gate); optional per-PR →
gate on ZAP's built-in new-alert count.** This deliberately keeps chargate's
net-new gate as a *SAST/SCA* concept and doesn't overload it onto DAST.

---

## 7. Rollout phases

**Crawl (week 1–2) — passive, one target, prove the pipe.**
- Scaffold `dastgate` repo + Dockerfile + urllib uploader (copy chargate's
  uploader almost verbatim).
- One nightly CronJob: **ZAP baseline (passive)** against `defectdojo.magmamoose.com`
  (safe, non-destructive, and dog-foods the hub).
- Confirm `ZAP Scan` reimport lands in DefectDojo with `auto_create_context`.
- **First PR:** `dastgate` repo scaffold + Helm chart + ESO `ExternalSecret` for
  a single-target `targets.yaml` + the nightly baseline CronJob. Small,
  reviewable, no active scanning, no auth yet.

**Walk (week 3–5) — add Nuclei + auth + staging active.**
- Add Nuclei nightly (templated + known-CVE) → `Nuclei Scan` reimport.
- Wire **browser-based OIDC auth** for one staging app (authentik `scanbot`
  user in OCI Vault); validate ZAP holds the session.
- Add the **weekly full-active** CronJob against staging only.
- Reuse the DT-sync **GitHub-issue auto-push** for new High/Crit DAST findings.

**Run (week 6+) — fleet + API + opt-in CI.**
- Expand `targets.yaml` to all `*.magmamoose.com` apps (passive prod / active
  staging).
- Add **`openapi` + Nuclei `-dast`** API scanning for services with specs; add
  **Schemathesis** as a CI test for those same specs (generic import).
- Publish the **reusable DAST workflow** (§5.8) for repos wanting per-PR API DAST.
- Tune `alertFilter` + DefectDojo SLA policies; graduate active scans from
  "manual-trigger" to scheduled once noise is understood.

---

## 8. Relationship to the rest of the MagmaMoose security program

- **[chargate](https://github.com/MagmaMoose/chargate)** — PR-time SAST/SCA/IaC/
  secrets gate (MegaLinter + net-new diff gating). dastgate is its runtime
  complement; shared DefectDojo uploader ethos, otherwise independent.
- **[securitybridge](https://github.com/MagmaMoose/securitybridge)** — the
  long-lived Dependency-Track ↔ DefectDojo sync backend (the "finding bus").
  dastgate reports into the same DefectDojo hub securitybridge maintains.
- **[security-platform](https://github.com/MagmaMoose/security-platform)** — the
  program index + security-tooling roadmap tying chargate, securitybridge, and
  dastgate together.
- **DefectDojo** + **Dependency-Track** — self-hosted in the private infra repo;
  DefectDojo is the durable triage system of record and the sink all sources
  report into.

---

## Sources

- ZAP by Checkmarx maintenance/leadership — [zaproxy.org team](https://www.zaproxy.org/docs/team/psiinon/), [Checkmarx+ZAP announcement](https://markets.financialcontent.com/wss/article/bizwire-2024-9-24-checkmarx-joins-forces-with-zap-to-supercharge-dynamic-application-security-testing-dast-for-the-enterprise-and-enhance-community-growth)
- ZAP Automation Framework + jobs/auth — [AF docs](https://www.zaproxy.org/docs/automate/automation-framework/), [AF authentication](https://www.zaproxy.org/docs/desktop/addons/automation-framework/authentication/), [browser-based auth](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/browser-auth/)
- ZAP GitHub Actions — [action-full-scan](https://github.com/zaproxy/action-full-scan), [action-baseline](https://github.com/zaproxy/action-baseline), [action-api-scan](https://github.com/zaproxy/action-api-scan)
- Nuclei DAST/fuzzing/auth — [nuclei repo](https://github.com/projectdiscovery/nuclei), [fuzzing v3.2 blog](https://projectdiscovery.io/blog/nuclei-fuzzing-for-unknown-vulnerabilities), [Swagger seeding](https://github.com/orgs/projectdiscovery/discussions/4987)
- DefectDojo parsers — [supported tools index](https://docs.defectdojo.com/supported_tools/parsers/), [Nuclei parser](https://docs.defectdojo.com/en/connecting_your_tools/parsers/file/nuclei/), [tests/reimport](https://docs.defectdojo.com/asset_modelling/engagements_tests/os__tests/)
- Tool status — [Wapiti](https://wapiti-scanner.github.io/), [Nikto](https://en.wikipedia.org/wiki/Nikto_(vulnerability_scanner)), [Arachni/w3af dead](https://geekflare.com/cybersecurity/open-source-web-security-scanner/), [StackHawk pricing](https://beaglesecurity.com/blog/article/stackhawk-pricing.html), [StackHawk review](https://appsecsanta.com/stackhawk), [StackHawk=ZAP](https://www.stackhawk.com/blog/guide-to-zap-application-security-testing/), [DAST pricing 2026](https://pentest.ae/dast-tools-comparison-2026/)
- Schemathesis — [site](https://schemathesis.io/), [repo](https://github.com/schemathesis/schemathesis)
