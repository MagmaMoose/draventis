# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/MagmaMoose/dastgate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MagmaMoose/dastgate/releases/tag/v0.1.0
