# Architecture

dastgate is a small Python CLI plus a Helm chart. The CLI is the
**orchestrator + uploader**; the scanning is done by external binaries (ZAP,
Nuclei) that live in the container image.

## Data flow

```
targets.yaml ──► config.load_config ──► Config (model.py)
                                          │
                 for each selected target │
                                          ▼
   zap.run_scan ──► zap.sh -autorun <plan> ──► /zap/wrk/zap-*.xml ─┐
   nuclei.run_scan ──► nuclei ...        ──► /zap/wrk/nuclei-*.jsonl ─┤
                                                                      ▼
                                          defectdojo.reimport ──► POST /api/v2/reimport-scan/
```

Per-target failures are isolated: one target failing (or one upload failing) does
not stop the rest.

## Modules (`src/dastgate/`)

| Module | Responsibility | Runtime deps |
|---|---|---|
| [`model.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/model.py) | Typed config dataclasses: `Target`, `AuthProfile`, `DefectDojoConfig`, `Config`, and the `ScanPolicy` / `Schedule` enums. | stdlib only |
| [`config.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/config.py) | Load & validate `targets.yaml` (or JSON) into a `Config`; apply defaults; reject dupes/missing fields. | PyYAML (lazy) |
| [`zap.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/zap.py) | Pick the AF plan for a policy, export `${DASTGATE_*}` env, build & run `zap.sh`, return the report path. | stdlib only |
| [`nuclei.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/nuclei.py) | Build & run the `nuclei` command (JSONL output; `-dast` for non-baseline). | stdlib only |
| [`defectdojo.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/defectdojo.py) | `reimport-scan` client: build multipart, POST via `urllib`, **failure-isolated**. | stdlib only |
| [`__main__.py`](https://github.com/MagmaMoose/dastgate/blob/main/src/dastgate/__main__.py) | The `dastgate run` CLI: parse args, select targets, orchestrate scan + upload. | None |

### Design properties

- **The DefectDojo client is stdlib `urllib` and never raises.** `reimport`
  returns a `ReimportResult(ok=…)`; the orchestrator logs and continues. A flaky
  DefectDojo never fails a scan.
- **Subprocess calls are injectable.** `zap.run_scan` / `nuclei.run_scan` take a
  `runner` callable (default `subprocess.run`), so command/env construction is
  unit-tested without invoking the real binaries. `--dry-run` builds everything
  and executes nothing.
- **Secrets never touch config or code paths that log.** Credentials are read
  from the environment by name (`auth.user_env` etc.); dastgate passes the env
  through to ZAP but does not read or print the values.
- **Policy → plan → report** is a single mapping in `zap.py`
  (`_PLAN_BY_POLICY`), so adding a policy is one table entry + one plan file.

## The CLI

```
dastgate run [--all | --target NAME] [--schedule nightly|weekly]
             [--config PATH] [--plans-dir DIR] [--workdir DIR]
             [--no-nuclei] [--dry-run]
```

Exit codes: `0` all selected targets attempted OK, `1` at least one scan failed
to produce a report, `2` bad arguments or config.

The CronJobs run `dastgate run --schedule <name>`, so each schedule scans only
its own targets.

## Automation plans (`automation/`)

One ZAP Automation Framework plan per policy. Each ends in a `report` job that
writes the traditional XML DefectDojo's `ZAP Scan` parser ingests. The target
URL (and, for authenticated plans, the login URL and credentials) is substituted
from the environment at plan-load time (`${DASTGATE_TARGET_URL}`, `${ZAP_USER}`,
…).

## The chart (`charts/dastgate/`)

Renders `targets.yaml` into a ConfigMap, provisions the secret backend (plain
Secret or ExternalSecret), and creates a CronJob per enabled schedule. See
[Deployment](deployment.md). The chart-rendered `targets.yaml` is the exact shape
`config.load_config` parses. The two are kept in sync.

## Testing

`tests/` mirrors the modules: config parsing & validation, the DefectDojo
multipart builder + failure isolation, ZAP/Nuclei command construction, and the
end-to-end CLI in `--dry-run`. Run `uv run pytest -q`.
