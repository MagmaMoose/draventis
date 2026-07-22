# automation/ - ZAP Automation Framework plans

Each file here is a **ZAP Automation Framework (AF) plan** - one declarative YAML
that orchestrates the crawl, scan, auth, and report steps. AF replaced the old
`zap-baseline` / `zap-full-scan` shell entry points and is the standard for every
dastgate job.

`dastgate` picks the plan for each target's `policy` (see
[`src/dastgate/zap.py`](../src/dastgate/zap.py)), exports the target URL into the
environment, and runs `zap.sh -cmd -autorun <plan>`.

## Plans

| Plan | Policy | Jobs | Destructive? | Run against |
|---|---|---|---|---|
| `zap-baseline.yaml` | `baseline` | `passiveScan-config` → `spider` → `passiveScan-wait` → `report` | No (passive) | production or staging |
| `full-active.yaml` | `full` | baseline + `spiderAjax` + `activeScan` | **Yes** (active) | **staging only** |
| `api-scan.yaml` | `api` | `openapi` import → spider → `activeScan` | Yes | staging services with an OpenAPI spec |

The target host is injected as `${DASTGATE_TARGET_URL}`; for authenticated plans,
`${DASTGATE_LOGIN_URL}`, `${ZAP_USER}` and `${ZAP_PASS}` are populated from the
environment (a mounted Secret). ZAP substitutes `${VAR}` at plan-load time. Every
value comes from config you control - never from a scanned response.

## How results flow to DefectDojo

Every plan ends in a `report` job that writes the **traditional XML** report ZAP's
DefectDojo parser ingests (e.g. `/zap/wrk/zap-baseline.xml`).
[`src/dastgate/defectdojo.py`](../src/dastgate/defectdojo.py) then POSTs it to
**`/api/v2/reimport-scan/`** (stdlib `urllib`, failure-isolated - an upload error
never fails the scan):

```
POST /api/v2/reimport-scan/   (multipart/form-data)
  scan_type            = "ZAP Scan"        # "Nuclei Scan" for Nuclei's JSON
  product_name         = <target.product>
  engagement_name      = "DAST - <target>"
  test_title           = "ZAP Scan"        # stable dedupe key across runs
  auto_create_context  = true              # DefectDojo creates product/engagement/test
  close_old_findings   = true              # fixed alerts auto-mitigate per engagement
  tags                 = dast,zap
```

**Reimport (not import)** is deliberate: DefectDojo dedupes against the existing
test, reactivates regressions, and (with `close_old_findings`) mitigates alerts
that disappeared - giving "what's new / fixed since last scan" without a
merge-base diff. See [`../docs/design.md`](../docs/design.md).

## Customising a plan

- **Exclude destructive routes** via `excludePaths` (logout, delete endpoints).
- **Suppress engine-level false positives** with an `alertFilter` job - committed
  here so it's versioned and reviewable.
- **Add authentication** with an `authentication` block on the context (browser
  method) plus a `verification` poll strategy so ZAP re-auths on session drop.
