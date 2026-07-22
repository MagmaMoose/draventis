"""Drive Nuclei — the fast, templated, low-false-positive complement to ZAP.

Nuclei emits JSONL that DefectDojo's ``Nuclei Scan`` parser ingests. As with
:mod:`dastgate.zap`, this module only builds and runs the command; the scanning
is Nuclei's job.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .model import Target

Runner = Callable[[list[str], Mapping[str, str]], int]


@dataclass(slots=True)
class NucleiArtifacts:
    command: list[str]
    report_path: Path
    returncode: int | None = None


def report_name(target: Target) -> str:
    return f"nuclei-{target.name}.jsonl"


def build_command(
    target: Target,
    report_path: Path,
    *,
    nuclei_cmd: str = "nuclei",
    dast: bool = False,
) -> list[str]:
    """Build the ``nuclei`` invocation for a target.

    ``-dast`` fuzzing is destructive-ish and is only enabled for non-baseline
    (staging) targets by the caller.
    """
    command = [
        nuclei_cmd,
        "-target",
        target.url,
        "-jsonl",
        "-output",
        str(report_path),
        "-silent",
    ]
    if target.openapi:
        command += ["-list", target.openapi]
    if dast:
        command += ["-dast"]
    return command


def _default_runner(command: list[str], env: Mapping[str, str]) -> int:
    return subprocess.run(command, env=dict(env), check=False).returncode


def run_scan(
    target: Target,
    *,
    workdir: str | os.PathLike[str],
    nuclei_cmd: str = "nuclei",
    dast: bool = False,
    base_env: Mapping[str, str] | None = None,
    dry_run: bool = False,
    runner: Runner | None = None,
) -> NucleiArtifacts:
    report_path = Path(workdir) / report_name(target)
    command = build_command(target, report_path, nuclei_cmd=nuclei_cmd, dast=dast)
    if dry_run:
        return NucleiArtifacts(command=command, report_path=report_path)
    env = dict(base_env if base_env is not None else os.environ)
    run = runner or _default_runner
    rc = run(command, env)
    return NucleiArtifacts(command=command, report_path=report_path, returncode=rc)
