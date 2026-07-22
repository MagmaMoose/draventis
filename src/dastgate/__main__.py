"""dastgate CLI — run scheduled DAST scans and reimport them into DefectDojo.

    dastgate run --all                 # scan every enabled target (default)
    dastgate run --target my-service   # scan one target
    dastgate run --all --no-upload     # scan only (CI smoke / dry run)

Exit codes: ``0`` all targets scanned · ``1`` a target failed to scan (tool error)
· ``2`` usage / no matching targets. A DefectDojo upload failure is **logged, not
fatal** (mirrors chargate) — the scan still counts as done.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from dastgate import __version__
from dastgate.config import DEFAULT_TARGETS_FILE, defectdojo_config_for, load_targets
from dastgate.defectdojo import upload_report
from dastgate.model import ScanOutcome, Target
from dastgate.zap import run_baseline


def _scan_one(
    target: Target,
    *,
    automation_dir: str,
    work_root: str,
    upload: bool = True,
) -> ScanOutcome:
    work_dir = os.path.join(work_root, target.name)
    try:
        report = run_baseline(target, automation_dir=automation_dir, work_dir=work_dir)
    except Exception as exc:  # per-target isolation — one bad target never aborts the run
        return ScanOutcome(target.name, False, False, None, f"scan error: {exc}")
    if report is None:
        return ScanOutcome(target.name, False, False, None, "ZAP produced no report")
    if not upload:
        return ScanOutcome(target.name, True, False, str(report), "scanned (upload skipped)")
    result = upload_report(defectdojo_config_for(target), report)
    message = result.message if result.ok else f"DefectDojo: {result.message}"
    if result.ok and result.url:
        message = f"{message} — {result.url}"
    return ScanOutcome(target.name, True, result.ok, str(report), message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dastgate", description="Scheduled DAST -> DefectDojo.")
    parser.add_argument("--version", action="version", version=f"dastgate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run scans against configured targets.")
    group = run.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Scan every enabled target (default).")
    group.add_argument("--target", help="Scan only the named target.")
    run.add_argument(
        "--targets-file",
        default=os.environ.get("DASTGATE_TARGETS_FILE", DEFAULT_TARGETS_FILE),
        help="YAML target list (default: $DASTGATE_TARGETS_FILE, else /etc/dastgate/targets.yaml).",
    )
    run.add_argument(
        "--automation-dir",
        default=os.environ.get("DASTGATE_AUTOMATION_DIR", "automation"),
        help="Directory holding the ZAP Automation Framework plan templates.",
    )
    run.add_argument(
        "--no-upload", action="store_true", help="Scan only; do not upload to DefectDojo."
    )
    args = parser.parse_args(argv)

    try:
        targets = load_targets(args.targets_file)
    except OSError as exc:
        print(f"dastgate: cannot read targets file {args.targets_file}: {exc}", file=sys.stderr)
        return 2
    if args.target:
        targets = [t for t in targets if t.name == args.target]
    if not targets:
        print("dastgate: no matching enabled targets", file=sys.stderr)
        return 2

    # Prefer the mounted scan workdir (the chart mounts an emptyDir at /zap/wrk);
    # fall back to a temp dir for local runs.
    work_root = os.environ.get("DASTGATE_WORK_DIR") or tempfile.mkdtemp(prefix="dastgate-")
    os.makedirs(work_root, exist_ok=True)
    outcomes = [
        _scan_one(
            t,
            automation_dir=args.automation_dir,
            work_root=work_root,
            upload=not args.no_upload,
        )
        for t in targets
    ]

    failed = 0
    for outcome in outcomes:
        status = "OK" if outcome.ok else ("scanned" if outcome.scanned else "FAILED")
        print(f"dastgate: [{outcome.target}] {status} — {outcome.message}")
        if not outcome.scanned:
            failed += 1
    print(f"dastgate: {len(outcomes) - failed}/{len(outcomes)} target(s) scanned")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
