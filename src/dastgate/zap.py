"""Render + run an OWASP ZAP Automation Framework plan, producing an XML report.

The subprocess boundary lives here (``runner`` is injectable) so the plan
rendering stays pure and unit-testable without ZAP installed.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from dastgate.model import Target

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

REPORT_FILE = "zap-report"  # the AF report job writes <REPORT_FILE>.xml


def _default_runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    # check=False: ZAP baseline exits non-zero when it finds alerts; that is a
    # normal outcome for a passive scan, not a tool error. We judge success by
    # whether the report file was produced, not by the exit code.
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _substitute(node: Any, subs: dict[str, str]) -> Any:
    """Recursively replace placeholder tokens inside string leaves of a parsed plan."""
    if isinstance(node, dict):
        return {k: _substitute(v, subs) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, subs) for v in node]
    if isinstance(node, str):
        for token, value in subs.items():
            node = node.replace(token, value)
        return node
    return node


def render_plan(
    template: str,
    *,
    target_url: str,
    report_dir: str,
    report_file: str = REPORT_FILE,
) -> str:
    """Inject the target/report values into an AF plan **as YAML values**.

    The template is parsed and re-dumped (``yaml.safe_load`` → substitute →
    ``yaml.safe_dump``) so a hostile or malformed target URL is always emitted as a
    safe, quoted scalar and can never inject Automation-Framework YAML (e.g. a
    sneaked-in ``activeScan`` job). The scope token ``${TARGET_SCOPE_REGEX}`` is
    regex-escaped + anchored so an unescaped ``.`` can't widen the crawl scope to
    look-alike hosts.
    """
    subs = {
        "${TARGET_URL}": target_url,
        "${TARGET_SCOPE_REGEX}": re.escape(target_url) + ".*",
        "${REPORT_DIR}": report_dir,
        "${REPORT_FILE}": report_file,
    }
    plan = _substitute(yaml.safe_load(template), subs)
    return yaml.safe_dump(plan, sort_keys=False, default_flow_style=False, allow_unicode=True)


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
