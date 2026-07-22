"""Load and validate ``targets.yaml`` into the typed :mod:`dastgate.model`.

The config file is the single source of truth for *what* to scan. In a cluster
it is supplied as a mounted file (a plain Kubernetes Secret by default, or
materialised from an external secret store). Secrets themselves (DefectDojo
token, per-target scan credentials) are read from the environment, not from this
file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .model import (
    AuthProfile,
    Config,
    DefectDojoConfig,
    ScanPolicy,
    Schedule,
    Target,
)


class ConfigError(ValueError):
    """Raised when ``targets.yaml`` is missing required fields or malformed."""


def _load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # JSON is a subset of YAML and needs no third-party parser; try it first so
    # the common ``.json`` case (and pure-JSON YAML) works with zero deps.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _load_yaml(text)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top-level document must be a mapping")
    return data


def _load_yaml(text: str) -> Any:
    try:
        import yaml  # optional dep, imported lazily
    except ModuleNotFoundError as exc:  # pragma: no cover - env-specific
        raise ConfigError(
            "PyYAML is required to read YAML config; install dastgate with its "
            "runtime dependencies, or supply the config as JSON."
        ) from exc
    return yaml.safe_load(text)


def _parse_auth(raw: dict[str, Any] | None) -> AuthProfile:
    if not raw:
        return AuthProfile()
    return AuthProfile(
        type=str(raw.get("type", "none")),
        login_url=raw.get("login_url"),
        user_env=str(raw.get("user_env", "ZAP_USER")),
        pass_env=str(raw.get("pass_env", "ZAP_PASS")),
        verify_url=raw.get("verify_url"),
    )


def _parse_target(raw: dict[str, Any], defaults: dict[str, Any]) -> Target:
    name = raw.get("name")
    url = raw.get("url")
    if not name:
        raise ConfigError("each target requires a 'name'")
    if not url:
        raise ConfigError(f"target {name!r} requires a 'url'")
    tags = raw.get("tags") or defaults.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return Target(
        name=str(name),
        url=str(url),
        product=raw.get("product"),
        policy=ScanPolicy.parse(raw.get("policy", defaults.get("policy"))),
        schedule=Schedule.parse(raw.get("schedule", defaults.get("schedule"))),
        openapi=raw.get("openapi"),
        auth=_parse_auth(raw.get("auth")),
        tags=list(tags),
    )


def _parse_defectdojo(raw: dict[str, Any] | None) -> DefectDojoConfig:
    raw = raw or {}
    # URL may also be supplied via the environment so the sink can be toggled at
    # deploy time without editing config.
    url = raw.get("url") or os.environ.get("DEFECTDOJO_URL")
    default = DefectDojoConfig()
    tags = raw.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return DefectDojoConfig(
        url=url,
        token_env=str(raw.get("token_env", default.token_env)),
        product_type=raw.get("product_type"),
        engagement_prefix=str(raw.get("engagement_prefix", default.engagement_prefix)),
        auto_create_context=bool(raw.get("auto_create_context", default.auto_create_context)),
        close_old_findings=bool(raw.get("close_old_findings", default.close_old_findings)),
        tags=list(tags) if tags else list(default.tags),
    )


def parse_config(data: dict[str, Any]) -> Config:
    """Build a :class:`Config` from an already-parsed mapping."""
    defaults = data.get("defaults") or {}
    raw_targets = data.get("targets") or []
    if not isinstance(raw_targets, list):
        raise ConfigError("'targets' must be a list")
    targets = [_parse_target(t, defaults) for t in raw_targets]

    names = [t.name for t in targets]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ConfigError(f"duplicate target names: {', '.join(sorted(dupes))}")

    nuclei = data.get("nuclei") or {}
    return Config(
        targets=targets,
        defectdojo=_parse_defectdojo(data.get("defectdojo")),
        nuclei_enabled=bool(nuclei.get("enabled", False)),
    )


def load_config(path: str | os.PathLike[str]) -> Config:
    """Read and validate a config file (YAML or JSON) into a :class:`Config`."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {p}")
    return parse_config(_load_raw(p))
