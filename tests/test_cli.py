from __future__ import annotations

import json

import pytest

from draventis.__main__ import main

CONFIG = {
    "defaults": {"schedule": "nightly"},
    "defectdojo": {"url": "https://dojo.example.com"},
    "nuclei": {"enabled": True},
    "targets": [
        {"name": "site", "url": "https://site.example.com", "schedule": "nightly"},
        {
            "name": "app-staging",
            "url": "https://app.staging.example.com",
            "policy": "full",
            "schedule": "weekly",
        },
    ],
}


@pytest.fixture
def config_file(tmp_path):
    p = tmp_path / "targets.json"
    p.write_text(json.dumps(CONFIG), encoding="utf-8")
    return str(p)


def test_dry_run_all_prints_plan_and_upload(config_file, capsys):
    rc = main(["run", "--all", "--config", config_file, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "selected 2 target(s)" in out
    assert "zap.sh -cmd -autorun" in out
    assert "would reimport" in out
    # nuclei enabled -> nuclei command shown
    assert "nuclei" in out


def test_schedule_filter_selects_subset(config_file, capsys):
    rc = main(["run", "--schedule", "weekly", "--config", config_file, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "selected 1 target(s)" in out
    assert "app-staging" in out
    assert "full-active.yaml" in out


def test_target_filter(config_file, capsys):
    rc = main(["run", "--target", "site", "--config", config_file, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "selected 1 target(s)" in out
    assert "zap-baseline.yaml" in out


def test_unmatched_target_fails_loudly(config_file, capsys):
    # A typo'd --target must not silently exit 0 (green CronJob scanning nothing).
    rc = main(["run", "--target", "typoooo", "--config", config_file, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "nothing scanned" in out


def test_refuses_without_scope(config_file, capsys):
    rc = main(["run", "--config", config_file])
    out = capsys.readouterr().out
    assert rc == 2
    assert "refusing to run" in out


def test_bad_config_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"targets": [{"url": "https://x"}]}), encoding="utf-8")
    rc = main(["run", "--all", "--config", str(bad), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "config error" in out


def test_no_nuclei_flag_suppresses_nuclei(config_file, capsys):
    rc = main(["run", "--all", "--config", config_file, "--dry-run", "--no-nuclei"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "nuclei -target" not in out
