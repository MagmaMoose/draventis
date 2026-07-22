from __future__ import annotations

from pathlib import Path

from dastgate import nuclei, zap
from dastgate.model import AuthProfile, ScanPolicy, Target


def _target(**kw) -> Target:
    base = {"name": "app", "url": "https://app.example.com"}
    base.update(kw)
    return Target(**base)


def test_plan_for_policy():
    assert zap.plan_for_policy(ScanPolicy.BASELINE) == ("zap-baseline.yaml", "zap-baseline.xml")
    assert zap.plan_for_policy(ScanPolicy.FULL) == ("full-active.yaml", "zap-full.xml")
    assert zap.plan_for_policy(ScanPolicy.API) == ("api-scan.yaml", "zap-api.xml")


def test_build_env_exports_target_and_auth():
    t = _target(
        openapi="https://app.example.com/openapi.json",
        auth=AuthProfile(type="browser-oidc", login_url="https://app.example.com/login"),
    )
    env = zap.build_env(t, base_env={"PATH": "/usr/bin"})
    assert env["DASTGATE_TARGET_URL"] == "https://app.example.com"
    assert env["DASTGATE_OPENAPI_URL"].endswith("/openapi.json")
    assert env["DASTGATE_LOGIN_URL"].endswith("/login")
    assert env["PATH"] == "/usr/bin"  # base env preserved


def test_zap_build_command():
    cmd = zap.build_command(Path("/plans/zap-baseline.yaml"))
    assert cmd == ["zap.sh", "-cmd", "-autorun", "/plans/zap-baseline.yaml"]


def test_zap_run_scan_dry_run_does_not_execute():
    called = []

    def runner(command, env):  # should never be called in dry-run
        called.append(command)
        return 0

    art = zap.run_scan(
        _target(),
        plans_dir="automation",
        workdir="/zap/wrk",
        dry_run=True,
        runner=runner,
    )
    assert called == []
    assert art.report_path == Path("/zap/wrk/zap-baseline.xml")
    assert art.command[0] == "zap.sh"


def test_zap_run_scan_invokes_runner():
    seen = {}

    def runner(command, env):
        seen["command"] = command
        seen["url"] = env["DASTGATE_TARGET_URL"]
        return 0

    art = zap.run_scan(
        _target(policy=ScanPolicy.FULL),
        plans_dir="automation",
        workdir="/tmp/wrk",
        base_env={},
        runner=runner,
    )
    assert art.returncode == 0
    assert seen["url"] == "https://app.example.com"
    assert "full-active.yaml" in seen["command"][-1]


def test_nuclei_build_command_dast():
    cmd = nuclei.build_command(_target(), Path("/wrk/nuclei-app.jsonl"), dast=True)
    assert cmd[0] == "nuclei"
    assert "-dast" in cmd
    assert "-jsonl" in cmd
    assert cmd[cmd.index("-output") + 1] == "/wrk/nuclei-app.jsonl"


def test_nuclei_command_ignores_openapi_url():
    # Nuclei's -list wants a local file of target URLs, not a spec URL, so the
    # openapi field must NOT leak into the command.
    t = _target(openapi="https://app.example.com/openapi.json")
    cmd = nuclei.build_command(t, Path("/wrk/nuclei-app.jsonl"))
    assert "-list" not in cmd
    assert "https://app.example.com/openapi.json" not in cmd


def test_nuclei_run_scan_dry_run():
    art = nuclei.run_scan(_target(), workdir="/wrk", dry_run=True)
    assert art.report_path == Path("/wrk/nuclei-app.jsonl")
    assert art.returncode is None
