# dastgate

Scheduled DAST for Kubernetes: a Python CLI runs OWASP ZAP (Automation Framework)
and Nuclei against already-deployed targets and reimports the reports into
DefectDojo. It ships as a generic Helm chart (a CronJob per schedule) and a
container image bundling the scanners. dastgate is the **orchestrator + uploader**;
the scanners are the engines. This is a **generic, public** project - no
org-specific hosts, secret stores, or infra in defaults.

## Commands

@.claude/QUICK_START.md

## Architecture

@.claude/ARCHITECTURE_MAP.md

## Gotchas

@.claude/COMMON_MISTAKES.md

## Finding code

- Before locating unfamiliar code, read `./PROJECT_INDEX.json` first (module +
  callgraph index).
- Load `.claude/decisions` and `.claude/sessions` ONLY when the task relates to
  them, never by default.
- Full human docs are in `./docs` (MkDocs); `.claude/*.md` is terse agent context.

## [tooling]

- Prefer targeted line-range reads over whole files; use `PROJECT_INDEX.json` to
  find the location.
- grep/find/glob: return matching paths and matched lines only.
- Commands that can flood output (helm template, pytest -v, docker build): pipe
  through `head`/`tail`/`grep` or redirect to `.claude/last_output.txt` and read
  ranges. Don't paste thousands of lines.
- After a successful write/edit, trust it; don't re-read just to "verify".

## [maintenance]

- Bug that took >1h: append to `.claude/COMMON_MISTAKES.md`.
- Architectural decision: run `/adr`.
- Public behaviour/API/config/setup changed: run `/update-docs`.
- `PROJECT_INDEX.json` stale (new module, big refactor): regenerate the affected
  modules section only.
- Keep `CLAUDE.md` under ~500 tokens; push detail into on-demand `.claude/` files.
