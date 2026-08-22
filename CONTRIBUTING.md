# Contributing

Thanks for your interest in draventis! Contributions are welcome.

## Development setup

Prerequisites: Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), Helm ≥ 3, Docker.

```bash
uv sync
uv run ruff check .          # lint
uv run pytest -q             # tests
helm lint charts/draventis    # chart
```

See [`docs/setup.md`](docs/setup.md) for the full local workflow and
[`docs/architecture.md`](docs/architecture.md) for the module map.

## Before you open a PR

- **Lint + tests pass:** `uv run ruff check . && uv run pytest -q`.
- **Chart still renders:** `helm lint charts/draventis` and
  `helm template dg charts/draventis`. If you change `values.yaml`, keep the
  chart-rendered `targets.yaml` loadable by the CLI (the round-trip in
  [`.claude/QUICK_START.md`](.claude/QUICK_START.md)).
- **Docs updated** if you changed behaviour, config, or setup (`docs/`).
- **Branch name** follows `<type>/<description>` (Conventional Commits types:
  `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, …).
- **Keep the core dependency-light:** the DefectDojo client is stdlib `urllib`;
  the only runtime dep is a YAML parser. Scanners are pinned binaries in the
  image, not Python deps.
- **Pin external GitHub Actions by commit SHA** with a `# vX.Y.Z` comment.

## Reporting security issues

Please follow [`SECURITY.md`](SECURITY.md). Do not open a public issue for
vulnerabilities.

## License

By contributing you agree your contributions are licensed under the project's
[MIT License](LICENSE).
