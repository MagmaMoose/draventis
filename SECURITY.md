# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via GitHub's [private vulnerability reporting](https://github.com/MagmaMoose/draventis/security/advisories/new)
("Report a vulnerability" under the repo's **Security** tab). If that is
unavailable, email the maintainer (see `pyproject.toml`) with `SECURITY` in the
subject.

Please include: affected version/commit, a description, reproduction steps or a
proof of concept, and the impact you foresee.

We aim to acknowledge within a few business days and to agree a coordinated
disclosure timeline with you.

## Scope

draventis is a **DAST orchestrator**: it runs scanners (OWASP ZAP, Nuclei) against
targets you configure and uploads results to DefectDojo. Especially relevant:

- Handling of scan **credentials** and the DefectDojo **token** (they must never
  be logged or leak into reports/manifests).
- The Helm chart's security posture (RBAC, `securityContext`, secret handling).
- The container image and its supply chain (base image, Nuclei download).

## Operating draventis safely

- Only point **active** policies (`full`, `api`) at non-production (staging)
  targets. `baseline` is passive and production-safe.
- Never scan a target you are not authorised to test.
- Targets and credentials must come only from configuration you control, never
  from a scanned response.

## Supported versions

This project is pre-1.0; only the latest release/`main` receives fixes.
