# dastgate

Scheduled **DAST** (Dynamic Application Security Testing) for Kubernetes:
[OWASP ZAP](https://www.zaproxy.org/) (via the ZAP Automation Framework) +
[Nuclei](https://github.com/projectdiscovery/nuclei) run on a schedule against
your already-deployed targets, with results reimported into
[DefectDojo](https://www.defectdojo.org/).

Deploy it to any cluster with Helm, point it at your URLs, and it does the rest.

## What it does

dastgate is an **orchestrator + uploader**. It runs as one or more Kubernetes
CronJobs; on each run it reads `targets.yaml`, scans each target with ZAP (and
optionally Nuclei), and reimports the reports into DefectDojo.

```
CronJob (nightly / weekly)
  └─ dastgate run --schedule <name>
       ├─ for each target: ZAP plan (by policy) → report.xml
       │                    Nuclei (optional)   → report.jsonl
       └─ reimport each report → DefectDojo /api/v2/reimport-scan/
```

## Why DAST

Static analysis reasons about source and artifacts *at rest*. DAST exercises the
**running** app: authN/session bugs, injection reachable only at runtime,
response-header/TLS/cookie posture, CORS, SSRF, live API surface, and drift
between the repo and what's actually deployed. See [Design](design.md).

## Get started

| I want to… | Go to |
|---|---|
| Deploy it to a cluster with Helm | [Deployment](deployment.md) |
| Understand `targets.yaml` and chart values | [Configuration](configuration.md) |
| Run/develop it locally | [Setup](setup.md) |
| Understand the code | [Architecture](architecture.md) |
| Understand *why* it's built this way | [Design](design.md) |

## Status

The orchestration, config model, DefectDojo uploader, ZAP/Nuclei command
building, Helm chart, and container image are implemented and unit-tested.
Validate the end-to-end scan path against your own environment before relying on
it. Start with a single `baseline` target against a safe host.

## License

MIT.
