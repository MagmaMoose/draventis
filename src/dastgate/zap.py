"""Drive the ZAP Automation Framework (``zap.sh -autorun``).

dastgate picks the AF plan for a target's policy, exports the target URL (and,
for authenticated plans, the scan credentials) into the environment that ZAP
substitutes ``${VAR}`` from, invokes ``zap.sh``, and returns the report path the
plan writes. The scanning itself is done by ZAP; this module is just the glue.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .model import ScanPolicy, Target

# Plan file + the report file that plan's `report` job writes, per policy.
_PLAN_BY_POLICY: dict[ScanPolicy, tuple[str, str]] = {
    ScanPolicy.BASELINE: ("zap-baseline.yaml", "zap-baseline.xml"),
    ScanPolicy.FULL: ("full-active.yaml", "zap-full.xml"),
    ScanPolicy.API: ("api-scan.yaml", "zap-api.xml"),
}

Runner = Callable[[list[str], Mapping[str, str]], int]


@dataclass(slots=True)
class ScanArtifacts:
    """What a ZAP run produced (or would produce, in dry-run)."""

    command: list[str]
    env: dict[str, str]
    report_path: Path
    returncode: int | None = None


def plan_for_policy(policy: ScanPolicy) -> tuple[str, str]:
    """Return ``(plan_filename, report_filename)`` for a scan policy."""
    try:
        return _PLAN_BY_POLICY[policy]
    except KeyError as exc:  # pragma: no cover - enum is closed
        raise ValueError(f"no ZAP plan for policy {policy!r}") from exc


def build_env(target: Target, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build the environment ZAP resolves ``${...}`` placeholders from."""
    env = dict(base_env if base_env is not None else os.environ)
    env["DASTGATE_TARGET_URL"] = target.url
    # ZAP `includePaths` are regexes, so a raw URL would leave every `.` in the
    # hostname as a live wildcard (scope-widening). Export a pre-escaped scope.
    env["DASTGATE_TARGET_SCOPE_REGEX"] = re.escape(target.url) + ".*"
    if target.openapi:
        env["DASTGATE_OPENAPI_URL"] = target.openapi
    if target.auth.enabled and target.auth.login_url:
        env["DASTGATE_LOGIN_URL"] = target.auth.login_url
    # ZAP_USER / ZAP_PASS are expected to already be present in base_env (from a
    # mounted Secret); we do not read or copy the values here.
    return env


def build_command(plan_path: Path, zap_cmd: str = "zap.sh") -> list[str]:
    """Build the ``zap.sh -cmd -autorun <plan>`` invocation."""
    return [zap_cmd, "-cmd", "-autorun", str(plan_path)]


def _default_runner(command: list[str], env: Mapping[str, str]) -> int:
    return subprocess.run(command, env=dict(env), check=False).returncode


def run_scan(
    target: Target,
    *,
    plans_dir: str | os.PathLike[str],
    workdir: str | os.PathLike[str],
    zap_cmd: str = "zap.sh",
    base_env: Mapping[str, str] | None = None,
    dry_run: bool = False,
    runner: Runner | None = None,
) -> ScanArtifacts:
    """Run (or, with ``dry_run``, only plan) a ZAP scan for one target."""
    plan_file, report_file = plan_for_policy(target.policy)
    plan_path = Path(plans_dir) / plan_file
    report_path = Path(workdir) / report_file
    command = build_command(plan_path, zap_cmd=zap_cmd)
    env = build_env(target, base_env)

    if dry_run:
        return ScanArtifacts(command=command, env=env, report_path=report_path)

    run = runner or _default_runner
    rc = run(command, env)
    return ScanArtifacts(command=command, env=env, report_path=report_path, returncode=rc)
