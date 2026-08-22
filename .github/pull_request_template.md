<!-- Branch name must follow <type>/<description> (feat, fix, docs, refactor, ...). -->

## What & why

<!-- What does this change and why? Link any issue. -->

## Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest -q` passes
- [ ] `helm lint charts/draventis` passes (if the chart changed)
- [ ] Docs updated (`docs/`) for any behaviour/config/setup change
- [ ] No secrets, tokens, or real hostnames committed
- [ ] External GitHub Actions pinned by commit SHA with a `# vX.Y.Z` comment
