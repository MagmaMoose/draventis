# draventis

[![CI](https://github.com/MagmaMoose/draventis/actions/workflows/ci.yml/badge.svg)](https://github.com/MagmaMoose/draventis/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-draventis-3f51b5)](https://docs.magmamoose.com/draventis/)
[![License](https://img.shields.io/github/license/MagmaMoose/draventis)](LICENSE)

> **Scheduled DAST for Kubernetes, with the results in DefectDojo.**

## What it is

Static analysis reasons about source and artifacts at rest; it never sends an HTTP
request to a running instance. draventis closes that gap.
[OWASP ZAP](https://www.zaproxy.org/) (driven by the ZAP Automation Framework) and
[Nuclei](https://github.com/projectdiscovery/nuclei) run on a schedule against your
already-deployed targets, and the findings are reimported into
[DefectDojo](https://www.defectdojo.org/).

Two surfaces: a Helm chart that installs the CronJobs, and the Python CLI those jobs
run. They talk through the chart's rendered config; neither imports the other.

> **`policy: full` sends active attacks. Never point it at production.** `baseline` is
> passive and production-safe; `full` and `api` actively attack the target and belong on
> staging only. Nothing stops you setting it wrong, so set it deliberately —
> see [Configuration](https://docs.magmamoose.com/draventis/configuration/).

## Run it

```bash
helm install draventis ./charts/draventis \
  --namespace security --create-namespace \
  --set defectDojo.url=https://defectdojo.example.com \
  --set secret.defectDojoToken=$DEFECTDOJO_TOKEN \
  --set targets[0].name=my-site \
  --set targets[0].url=https://my-site.example.com \
  --set targets[0].policy=baseline
```

Point it at your URLs and it does the rest. For a values file, authenticated scanning,
or running a scan locally, see [Setup](https://docs.magmamoose.com/draventis/setup/).

## Documentation

| | |
| --- | --- |
| [Setup](https://docs.magmamoose.com/draventis/setup/) | Install, run a scan locally, authenticated scanning |
| [Configuration](https://docs.magmamoose.com/draventis/configuration/) | Targets, scan policies, schedules, every value |
| [Deployment](https://docs.magmamoose.com/draventis/deployment/) | Running it in a cluster |
| [Architecture](https://docs.magmamoose.com/draventis/architecture/) · [Design](https://docs.magmamoose.com/draventis/design/) | How it works, and why it is shaped this way |

## Status

The orchestration, config model, DefectDojo uploader, ZAP/Nuclei command
building, Helm chart, and container image are implemented and unit-tested.
Validate the end-to-end scan path against your own environment before relying on
it. Start with a single `baseline` target against a safe host.

## Where it sits

**draventis** scans what is deployed · [Chargate](https://github.com/MagmaMoose/chargate)
gates security at the pull request · [Ponvara](https://github.com/MagmaMoose/ponvara)
routes findings between systems

## Security · Contributing · License

[Report a vulnerability](https://github.com/MagmaMoose/draventis/security/advisories/new) ·
[Contributing](https://github.com/MagmaMoose/.github/blob/main/CONTRIBUTING.md) ·
Apache-2.0, see [LICENSE](LICENSE)
