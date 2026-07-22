"""Typed value objects for dastgate (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    """A single DAST target: what to scan, and where its findings land."""

    name: str  # DefectDojo product name (and log label)
    url: str  # base URL to scan
    plan: str = "zap-baseline"  # automation/<plan>.yaml to run
    engagement: str = "DAST"  # DefectDojo engagement name
    enabled: bool = True


@dataclass(frozen=True)
class ScanOutcome:
    """Result of scanning + uploading one target."""

    target: str
    scanned: bool  # ZAP produced a report
    uploaded: bool  # DefectDojo accepted it
    report_path: str | None
    message: str

    @property
    def ok(self) -> bool:
        return self.scanned and self.uploaded
