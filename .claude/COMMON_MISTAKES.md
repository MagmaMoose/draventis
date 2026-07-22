# Common mistakes / footguns

- **This is generic + public.** No org-specific hosts, secret stores, ingress, or
  sister projects in defaults. Use `example.com`, "your cluster", "your secret
  store". The only kept identity is the repo URL, author, and `ghcr.io/magmamoose`
  image namespace.
- **`full`/`api` policies are ACTIVE (destructive) - staging only.** Never a
  default, never pointed at production. `baseline` is passive/prod-safe.
- **Secrets never live in `targets.yaml` or code.** DefectDojo token + scan creds
  come from env (`DEFECTDOJO_TOKEN`, `ZAP_USER`/`ZAP_PASS`). Never read a
  credential from a scanned response. Never log credential values.
- **DefectDojo client must never raise.** `defectdojo.reimport` returns
  `ReimportResult(ok=…)`; the orchestrator logs and continues. An upload failure
  must not fail a scan.
- **Chart ↔ config must stay in sync.** `templates/configmap.yaml` renders the
  exact `targets.yaml` shape `config.py` parses. Change one → change the other
  and re-run the round-trip check (see QUICK_START).
- **Adding a scan policy = one enum + one table row + one plan.** `ScanPolicy`
  (model), `_PLAN_BY_POLICY` (zap.py), a plan file in `automation/`.
- **Keep the core dep-free.** Only runtime dep is PyYAML (lazy). ZAP + Nuclei are
  pinned binaries in the image; DefectDojo is stdlib `urllib`.
- **`ruff` selects E,F,I,UP,B,SIM,RUF** - no `# noqa` for non-selected codes
  (RUF100). Enums are `StrEnum` (py3.11+), not `(str, Enum)`.
- **Can't run ZAP/Nuclei here.** Validate command/env construction via unit tests
  + `--dry-run`; the real binary path is only exercised in-cluster.
