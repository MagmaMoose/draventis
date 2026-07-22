"""Render + run an OWASP ZAP Automation Framework plan, producing an XML report.

The subprocess boundary lives here (``runner`` is injectable) so the plan
rendering stays pure and unit-testable without ZAP installed.
"""

from __future__ import annotations

import string
import subprocess
from collections.abc import Callable
from pathlib import Path

from dastgate.model import Target

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

REPORT_FILE = "zap-report"  # the AF report job writes <REPORT_FILE>.xml


def _default_runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    # check=False: ZAP baseline exits non-zero when it finds alerts; that is a
    # normal outcome for a passive scan, not a tool error. We judge success by
    # whether the report file was produced, not by the exit code.
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def render_plan(
    template: str,
    *,
    target_url: str,
    report_dir: str,
    report_file: str = REPORT_FILE,
) -> str:
    """Substitute ``${TARGET_URL}`` / ``${REPORT_DIR}`` / ``${REPORT_FILE}``."""
    return string.Template(template).safe_substitute(
        TARGET_URL=target_url, REPORT_DIR=report_dir, REPORT_FILE=report_file
    )


def run_baseline(
    target: Target,
    *,
    automation_dir: str | Path,
    work_dir: str | Path,
    zap_cmd: str = "zap.sh",
    runner: Runner | None = None,
) -> Path | None:
    """Render the target's AF plan, run ZAP, and return the report path if produced."""
    runner = runner or _default_runner
    automation_dir = Path(automation_dir)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    template = (automation_dir / f"{target.plan}.yaml").read_text()
    plan = render_plan(template, target_url=target.url, report_dir=str(work_dir))
    plan_path = work_dir / f"{target.plan}.rendered.yaml"
    plan_path.write_text(plan)

    runner([zap_cmd, "-cmd", "-autorun", str(plan_path)])

    report = work_dir / f"{REPORT_FILE}.xml"
    return report if report.is_file() else None
