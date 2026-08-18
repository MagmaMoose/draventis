# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Renamed `dastgate` → `draventis`.** The `-gate` suffix collided with
  `chargate` and misdescribed the tool: this runs scheduled scans against
  deployed environments and reports, it does not gate a pipeline. Renames the
  Python package (`src/draventis`), the CLI entrypoint, the Helm chart, the
  image (`ghcr.io/magmamoose/draventis`) and every `DASTGATE_*` environment
  variable to `DRAVENTIS_*`. No published container image or live deployment
  existed under the old name, so nothing needs migrating; GitHub redirects the
  old repository URL.

## [0.1.0] - 2026-07-22

First working release: dastgate moves out of the Phase 0 scaffold into a real,
generic, deploy-anywhere project.

### Added

- `dastgate run` CLI: load `targets.yaml`, select targets by name/schedule, run
  ZAP (and optionally Nuclei) per target, and reimport reports into DefectDojo.
- Stdlib-`urllib`, failure-isolated DefectDojo `reimport-scan` client.
- ZAP Automation Framework plans for the `baseline`, `full`, and `api` policies.
- A generic Helm chart (chart `0.2.0`): ConfigMap-rendered `targets.yaml`, a
  plain Secret by default with optional External Secrets Operator, a CronJob per
  schedule, a minimal-RBAC ServiceAccount, and `values.schema.json`.
- A container image (`Dockerfile`) bundling ZAP + headless browsers + Nuclei +
  the CLI, pinned by digest and arch-correct.
- MkDocs documentation site and a unit-test suite.

[Unreleased]: https://github.com/MagmaMoose/draventis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MagmaMoose/draventis/releases/tag/v0.1.0
