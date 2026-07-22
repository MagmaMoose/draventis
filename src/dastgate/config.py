"""Load DAST targets (YAML) and build the DefectDojo config (environment)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from dastgate.defectdojo import DefectDojoConfig
from dastgate.model import Target

DEFAULT_TARGETS_FILE = "/etc/dastgate/targets.yaml"


def load_targets(path: str | Path) -> list[Target]:
    """Parse the targets YAML into the list of **enabled** targets.

    Expected shape (the single OCI-Vault ``dastgate-targets`` key, mounted as
    ``targets.yaml`` — see docs/DESIGN.md §5.3)::

        targets:
          - name: my-service            # DefectDojo product
            url: https://my-service.magmamoose.com
            plan: zap-baseline          # optional (automation/<plan>.yaml)
            engagement: DAST            # optional
            enabled: true               # optional (default true)
    """
    data = yaml.safe_load(Path(path).read_text()) or {}
    raw = data.get("targets") or []
    targets: list[Target] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        url = entry.get("url")
        if not name or not url:
            continue
        target = Target(
            name=str(name),
            url=str(url),
            plan=str(entry.get("plan", "zap-baseline")),
            engagement=str(entry.get("engagement", "DAST")),
            enabled=bool(entry.get("enabled", True)),
        )
        if target.enabled:
            targets.append(target)
    return targets


def defectdojo_config_for(target: Target, *, scan_type: str = "ZAP Scan") -> DefectDojoConfig:
    """Build a :class:`DefectDojoConfig` for a target from the environment.

    ``DEFECTDOJO_URL`` / ``DEFECTDOJO_TOKEN`` are required (the uploader returns
    ``ok=False`` if either is empty); the rest have sane defaults.
    """
    return DefectDojoConfig(
        base_url=os.environ.get("DEFECTDOJO_URL", "").rstrip("/"),
        token=os.environ.get("DEFECTDOJO_TOKEN", ""),
        product_name=target.name,
        product_type_name=os.environ.get("DD_PRODUCT_TYPE", "DAST"),
        engagement_name=target.engagement,
        scan_type=scan_type,
        test_title="ZAP baseline",  # stable reimport key: one Test per engagement
        close_old_findings=os.environ.get("DD_CLOSE_OLD", "true").lower() != "false",
        verify_ssl=os.environ.get("DD_INSECURE", "").lower() not in ("1", "true"),
    )
