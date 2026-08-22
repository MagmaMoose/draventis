# Architecture map

draventis is an **orchestrator + uploader**, not a scanner. A Python CLI
(`src/draventis/`) reads `targets.yaml`, runs external scanners (ZAP, Nuclei) that
live in the container image, and reimports their reports into DefectDojo.

Flow: `config.load_config` → `Config` (model) → for each selected target
`zap.run_scan` / `nuclei.run_scan` produce a report → `defectdojo.reimport` POSTs
it to `/api/v2/reimport-scan/`. `__main__` orchestrates with per-target failure
isolation; the DefectDojo client is stdlib `urllib` and never raises.

Modules: `model` (typed config), `config` (load/validate YAML), `zap`/`nuclei`
(build + run the binary, runner injectable, `--dry-run` builds nothing runs),
`defectdojo` (multipart reimport), `__main__` (the `run` CLI).

Deploy surface: `charts/draventis/` renders `targets.yaml` into a ConfigMap,
provisions a plain Secret (default) or ExternalSecret (optional), and creates a
CronJob per enabled schedule (`nightly`/`weekly`). Scan credentials + DefectDojo
token come from env, never from config or a scanned response. Scan policy
(`baseline`/`full`/`api`) → one ZAP AF plan in `automation/`.

Read `docs/architecture.md` for the full version; `./PROJECT_INDEX.json` for the
module/callgraph index.
