# Quick start (most-run commands)

```bash
uv sync                                        # install deps + dev tools
uv run ruff check .                            # lint
uv run ruff check . --fix                      # lint + autofix
uv run pytest -q                               # unit tests
cp targets.example.yaml targets.local.yaml                        # first time
uv run dastgate run --all --config targets.local.yaml --dry-run   # plan, no scan

helm lint charts/dastgate                      # lint the chart
helm template dg charts/dastgate               # render manifests
helm template dg charts/dastgate --show-only templates/configmap.yaml   # see targets.yaml

docker build -t dastgate:local .               # build the scanner image

mkdocs serve                                   # docs preview (needs mkdocs-material)
mkdocs build                                   # render ./docs -> ./site (gitignored)
```

Chart↔config round-trip check (rendered `targets.yaml` must load in the CLI):

```bash
helm template dg charts/dastgate --show-only templates/configmap.yaml \
  | python3 -c "import sys,yaml;print(yaml.safe_load(sys.stdin)['data']['targets.yaml'])" \
  | tee /tmp/t.yaml >/dev/null
uv run dastgate run --all --config /tmp/t.yaml --plans-dir automation --dry-run
```
