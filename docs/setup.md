# Setup (local development)

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (package + venv manager)
- Docker (to build the scanner image)
- Helm ≥ 3 (to lint/template the chart)

## Install & test

```bash
uv sync                 # create the venv and install deps + dev tools
uv run ruff check .     # lint
uv run pytest -q        # unit tests
```

## Run the CLI locally

The CLI orchestrates scans and uploads. Locally you will not have `zap.sh` /
`nuclei` on your `PATH`, so use `--dry-run` to exercise config parsing, plan
selection, and the upload plan without running anything. Start from the shipped
example (`targets.local.yaml` is gitignored):

```bash
cp targets.example.yaml targets.local.yaml    # then edit it
uv run dastgate run --all --config targets.local.yaml --dry-run
```

A minimal config looks like:

```yaml
defectdojo:
  url: https://defectdojo.example.com
targets:
  - name: my-site
    url: https://my-site.example.com
    policy: baseline
    schedule: nightly
```

Selection flags:

- `--all`: every target
- `--target <name>`: one target
- `--schedule <nightly|weekly>`: only targets on that schedule (this is what the
  CronJobs use)

Other useful flags: `--config`, `--plans-dir`, `--workdir`, `--no-nuclei`,
`--dry-run`. Run `uv run dastgate run --help` for the full list.

## Build the scanner image

The real scanning happens inside the container, which bundles ZAP + headless
browsers + Nuclei + the CLI:

```bash
docker build -t dastgate:local .

docker run --rm \
  -e DEFECTDOJO_TOKEN=$DEFECTDOJO_TOKEN \
  -v "$PWD/targets.yaml:/config/targets.yaml:ro" \
  dastgate:local run --all --config /config/targets.yaml --dry-run
```

Pin the Nuclei release at build time with `--build-arg NUCLEI_VERSION=x.y.z`.

## Documentation site

```bash
pip install mkdocs-material      # one-time
mkdocs serve                     # live preview at http://127.0.0.1:8000
mkdocs build                     # render static site to ./site (gitignored)
```

## Layout

```
src/dastgate/      # the CLI + modules (see Architecture)
tests/             # unit tests, one file per concern
automation/        # ZAP Automation Framework plans (one per policy)
charts/dastgate/   # the Helm chart
docs/              # this documentation
Dockerfile         # the scanner image
```
