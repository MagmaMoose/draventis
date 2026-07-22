"""dastgate CLI — ``dastgate run``.

Loads ``targets.yaml``, selects targets by name/schedule, runs ZAP (and
optionally Nuclei) against each, and reimports the reports into DefectDojo.
Per-target failures are isolated: one target failing does not stop the rest.

Examples
--------
    dastgate run --all
    dastgate run --schedule nightly
    dastgate run --target app-staging
    dastgate run --all --dry-run        # print plans + upload shape, run nothing
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from . import __version__, defectdojo, nuclei, zap
from .config import ConfigError, load_config
from .model import Config, ScanPolicy, Schedule, Target

DEFAULT_CONFIG = "targets.yaml"
DEFAULT_PLANS_DIR = "automation"
DEFAULT_WORKDIR = "/zap/wrk"


def _log(msg: str) -> None:
    print(f"[dastgate] {msg}", flush=True)


def _scan_type_and_report(kind: str) -> str:
    return {"zap": "ZAP Scan", "nuclei": "Nuclei Scan"}[kind]


def _upload(cfg: Config, target: Target, report_path: Path, kind: str, *, dry_run: bool) -> None:
    dd = cfg.defectdojo
    if not dd.enabled:
        _log(f"  DefectDojo sink disabled (no url); skipping upload of {report_path.name}")
        return
    scan_type = _scan_type_and_report(kind)
    token = os.environ.get(dd.token_env, "")
    tags = sorted({*dd.tags, *target.tags, kind})
    if dry_run:
        _log(
            f"  would reimport {report_path.name} -> {dd.url} "
            f"(scan_type={scan_type!r}, product={target.product_name()!r}, "
            f"engagement={dd.engagement_for(target)!r}, tags={tags})"
        )
        return
    if not token:
        _log(f"  WARNING: {dd.token_env} is empty; skipping upload of {report_path.name}")
        return
    result = defectdojo.reimport(
        base_url=dd.url or "",
        token=token,
        scan_type=scan_type,
        report_path=report_path,
        product_name=target.product_name(),
        engagement_name=dd.engagement_for(target),
        test_title=scan_type,
        tags=tags,
        product_type=dd.product_type,
        auto_create_context=dd.auto_create_context,
        close_old_findings=dd.close_old_findings,
    )
    if result.ok:
        link = f" — {result.url}" if result.url else ""
        _log(f"  reimported {report_path.name} (HTTP {result.status}){link}")
    else:
        _log(f"  upload failed (non-fatal): {result.error}")


def scan_target(
    cfg: Config,
    target: Target,
    *,
    plans_dir: str,
    workdir: str,
    run_nuclei: bool,
    dry_run: bool,
) -> bool:
    """Scan one target and upload its report(s). Returns False on scan failure."""
    _log(f"target {target.name} ({target.policy.value}) -> {target.url}")
    ok = True

    artifacts = zap.run_scan(
        target, plans_dir=plans_dir, workdir=workdir, dry_run=dry_run
    )
    if dry_run:
        _log(f"  zap: {' '.join(artifacts.command)}")
    elif artifacts.returncode not in (0, None) and not artifacts.report_path.exists():
        # ZAP exits non-zero when it finds alerts too; treat only a hard failure
        # (no report written) as an error.
        _log(f"  ZAP failed (rc={artifacts.returncode}, no report); skipping upload")
        ok = False
    if ok:
        _upload(cfg, target, artifacts.report_path, "zap", dry_run=dry_run)

    if run_nuclei and cfg.nuclei_enabled:
        dast = target.policy is not ScanPolicy.BASELINE
        nart = nuclei.run_scan(target, workdir=workdir, dast=dast, dry_run=dry_run)
        if dry_run:
            _log(f"  nuclei: {' '.join(nart.command)}")
        _upload(cfg, target, nart.report_path, "nuclei", dry_run=dry_run)

    return ok


def orchestrate(cfg: Config, args: argparse.Namespace) -> int:
    schedule = Schedule.parse(args.schedule) if args.schedule else None
    targets = cfg.select(name=args.target, schedule=schedule)
    if not targets:
        _log(
            "no targets matched selection "
            f"(target={args.target!r}, schedule={args.schedule!r}) — nothing scanned"
        )
        return 2
    _log(f"selected {len(targets)} target(s)")

    failures = 0
    for target in targets:
        try:
            if not scan_target(
                cfg,
                target,
                plans_dir=args.plans_dir,
                workdir=args.workdir,
                run_nuclei=args.nuclei,
                dry_run=args.dry_run,
            ):
                failures += 1
        except Exception as exc:  # isolate one target's failure
            failures += 1
            _log(f"  ERROR scanning {target.name} (non-fatal): {exc}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dastgate", description=__doc__)
    parser.add_argument("--version", action="version", version=f"dastgate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="scan targets and reimport into DefectDojo")
    scope = run.add_mutually_exclusive_group()
    scope.add_argument("--all", dest="all_targets", action="store_true", help="scan every target")
    scope.add_argument("--target", help="scan a single target by name")
    run.add_argument(
        "--schedule",
        choices=[s.value for s in Schedule],
        help="only targets on this schedule",
    )
    run.add_argument("--config", default=DEFAULT_CONFIG, help="path to targets.yaml")
    run.add_argument("--plans-dir", default=DEFAULT_PLANS_DIR, help="dir of ZAP AF plans")
    run.add_argument("--workdir", default=DEFAULT_WORKDIR, help="scan output dir")
    run.add_argument(
        "--no-nuclei", dest="nuclei", action="store_false", help="skip Nuclei even if enabled"
    )
    run.add_argument(
        "--dry-run", action="store_true", help="print what would run without executing"
    )
    run.set_defaults(nuclei=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":  # pragma: no cover - argparse enforces this
        return 2
    if not args.all_targets and not args.target and not args.schedule:
        _log("refusing to run: pass --all, --target NAME, or --schedule")
        return 2
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        _log(f"config error: {exc}")
        return 2
    return orchestrate(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())
