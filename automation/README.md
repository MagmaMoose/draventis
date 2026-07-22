# automation/ — ZAP Automation Framework plans

> **Phase 0 scaffold.** `zap-baseline.yaml` is an illustrative example only.
> Per-target plan templating (`src/dastgate/zap.py`) is not built yet — see
> [`../docs/DESIGN.md`](../docs/DESIGN.md) §5.

Each file here is a **ZAP Automation Framework (AF) plan** — one declarative YAML
that orchestrates the crawl, scan, auth, and report steps. AF replaced the old
`zap-baseline` / `zap-full-scan` shell entry points and is the standard for every
dastgate job.

## How plans map to scheduled scans

| Plan (planned) | Jobs | Destructive? | Where it runs | Schedule |
|---|---|---|---|---|
| `zap-baseline.yaml` (this dir) | `passiveScan-config` → `spider` → `passiveScan-wait` → `report` | No (passive only) | Prod-facing + staging hosts | **Nightly** |
| `full-active.yaml` (planned) | baseline + `spiderAjax` + `activeScan` | **Yes** (active attacks) | **Staging only** | **Weekly** |
| `api-scan.yaml` (planned) | `openapi` import → spider → `activeScan` | Yes | Staging services with an OpenAPI spec | Per-service |

The target host is injected as `${DASTGATE_TARGET_URL}` (and, for authenticated
plans, `${ZAP_USER}` / `${ZAP_PASS}`) via environment variables that External
Secrets Operator populates from OCI Vault. `src/dastgate/zap.py` will pick the
plan per target's `policy` (`baseline` | `full` | `api`) from `targets.yaml`,
render it, invoke `zap.sh -autorun`, and collect the report.

## How results flow to DefectDojo

Every plan ends in a `report` job that writes the **traditional XML** report ZAP's
DefectDojo parser ingests (`/zap/wrk/zap-baseline.xml`). `src/dastgate/defectdojo.py`
then POSTs it to **`/api/v2/reimport-scan/`** (stdlib `urllib`, failure-isolated —
an upload error never fails the scan), mirroring the chargate uploader and the
Dependency-Track ↔ DefectDojo sync:

```
POST /api/v2/reimport-scan/   (multipart/form-data)
  scan_type            = "ZAP Scan"        # "Nuclei Scan" for Nuclei's JSON
  product_name         = magmamoose/<app>
  engagement_name      = "DAST — <target>"
  test_title           = "ZAP Scan"        # stable dedupe key across runs
  auto_create_context  = true              # DefectDojo creates product/engagement/test on first run
  close_old_findings   = true              # fixed alerts auto-mitigate per engagement
  tags                 = dast,zap,staging
```

**Reimport (not import)** is deliberate: DefectDojo dedupes against the existing
test, reactivates regressions, and (with `close_old_findings`) mitigates alerts
that disappeared — giving "what's new / fixed since last scan" without a
merge-base diff. DefectDojo stays the durable triage system of record; false
positives and risk-acceptance are marked there once and survive nightly reimports.
