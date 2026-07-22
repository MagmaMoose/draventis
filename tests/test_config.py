from __future__ import annotations

import json

import pytest

from dastgate.config import ConfigError, load_config, parse_config
from dastgate.model import ScanPolicy, Schedule


def _base() -> dict:
    return {
        "defaults": {"policy": "baseline", "schedule": "nightly", "tags": ["dast"]},
        "defectdojo": {"url": "https://dojo.example.com", "product_type": "Example"},
        "nuclei": {"enabled": True},
        "targets": [
            {"name": "site", "url": "https://site.example.com"},
            {
                "name": "app-staging",
                "url": "https://app.staging.example.com",
                "product": "example/app",
                "policy": "full",
                "schedule": "weekly",
                "openapi": "https://app.staging.example.com/openapi.json",
                "auth": {"type": "browser-oidc", "login_url": "https://app.staging.example.com/login"},
            },
        ],
    }


def test_defaults_and_overrides_applied():
    cfg = parse_config(_base())
    assert cfg.nuclei_enabled is True
    site, app = cfg.targets
    # inherits defaults
    assert site.policy is ScanPolicy.BASELINE
    assert site.schedule is Schedule.NIGHTLY
    assert site.tags == ["dast"]
    assert site.product_name() == "site"  # falls back to name
    # per-target overrides win
    assert app.policy is ScanPolicy.FULL
    assert app.schedule is Schedule.WEEKLY
    assert app.product_name() == "example/app"
    assert app.auth.enabled is True
    assert app.auth.login_url.endswith("/login")


def test_defectdojo_sink_config():
    cfg = parse_config(_base())
    assert cfg.defectdojo.enabled is True
    assert cfg.defectdojo.product_type == "Example"
    assert cfg.defectdojo.engagement_for(cfg.targets[0]) == "DAST - site"


def test_sink_disabled_without_url():
    data = _base()
    data["defectdojo"] = {}
    cfg = parse_config(data)
    assert cfg.defectdojo.enabled is False


def test_missing_name_or_url_raises():
    with pytest.raises(ConfigError):
        parse_config({"targets": [{"url": "https://x.example.com"}]})
    with pytest.raises(ConfigError):
        parse_config({"targets": [{"name": "x"}]})


def test_duplicate_target_names_raise():
    data = _base()
    data["targets"].append({"name": "site", "url": "https://dup.example.com"})
    with pytest.raises(ConfigError, match="duplicate"):
        parse_config(data)


def test_unknown_policy_raises():
    with pytest.raises(ValueError, match="unknown policy"):
        parse_config({"targets": [{"name": "x", "url": "https://x", "policy": "nope"}]})


def test_load_config_reads_json(tmp_path):
    p = tmp_path / "targets.json"
    p.write_text(json.dumps(_base()), encoding="utf-8")
    cfg = load_config(p)
    assert len(cfg.targets) == 2


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")
