"""Typed configuration model for draventis.

These dataclasses are the in-memory shape of ``targets.yaml`` (see
``config.load_config``). They are deliberately dependency-free (stdlib only) so
the model can be imported anywhere without pulling in a YAML parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScanPolicy(StrEnum):
    """How aggressively a target may be scanned.

    ``BASELINE`` is passive-only (spider + passive rules, no attacks) and is safe
    against production. ``FULL`` adds the active scanner and ajax-spider and must
    only be pointed at non-production (staging) targets. ``API`` imports an
    OpenAPI/GraphQL spec and scans the described operations.
    """

    BASELINE = "baseline"
    FULL = "full"
    API = "api"

    @classmethod
    def parse(cls, value: str | None) -> ScanPolicy:
        if value is None:
            return cls.BASELINE
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:  # pragma: no cover - exercised via config tests
            allowed = ", ".join(p.value for p in cls)
            raise ValueError(f"unknown policy {value!r}; expected one of: {allowed}") from exc


class Schedule(StrEnum):
    """Which CronJob a target belongs to."""

    NIGHTLY = "nightly"
    WEEKLY = "weekly"

    @classmethod
    def parse(cls, value: str | None) -> Schedule:
        if value is None:
            return cls.NIGHTLY
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:  # pragma: no cover - exercised via config tests
            allowed = ", ".join(s.value for s in cls)
            raise ValueError(f"unknown schedule {value!r}; expected one of: {allowed}") from exc


@dataclass(slots=True)
class AuthProfile:
    """Optional authentication for a target.

    ``user_env`` / ``pass_env`` name the environment variables the credentials are
    read from at scan time. Credentials themselves are never stored in config —
    they come from the environment (a mounted Secret), never from a scanned
    response.
    """

    type: str = "none"
    login_url: str | None = None
    user_env: str = "ZAP_USER"
    pass_env: str = "ZAP_PASS"
    verify_url: str | None = None

    @property
    def enabled(self) -> bool:
        return self.type not in ("", "none")


@dataclass(slots=True)
class Target:
    """A single host/service to scan."""

    name: str
    url: str
    product: str | None = None
    policy: ScanPolicy = ScanPolicy.BASELINE
    schedule: Schedule = Schedule.NIGHTLY
    openapi: str | None = None
    auth: AuthProfile = field(default_factory=AuthProfile)
    tags: list[str] = field(default_factory=list)

    def product_name(self) -> str:
        """DefectDojo product name — defaults to the target name."""
        return self.product or self.name


@dataclass(slots=True)
class DefectDojoConfig:
    """DefectDojo reimport sink settings.

    The sink is *enabled by the presence of a URL* (``enabled``). The API token is
    read from the environment (``token_env``), never stored in config.
    """

    url: str | None = None
    token_env: str = "DEFECTDOJO_TOKEN"
    product_type: str | None = None
    engagement_prefix: str = "DAST - "
    auto_create_context: bool = True
    close_old_findings: bool = True
    tags: list[str] = field(default_factory=lambda: ["dast"])

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def engagement_for(self, target: Target) -> str:
        return f"{self.engagement_prefix}{target.name}"


@dataclass(slots=True)
class Config:
    """Top-level parsed configuration."""

    targets: list[Target] = field(default_factory=list)
    defectdojo: DefectDojoConfig = field(default_factory=DefectDojoConfig)
    nuclei_enabled: bool = False

    def select(
        self,
        *,
        name: str | None = None,
        schedule: Schedule | None = None,
    ) -> list[Target]:
        """Filter targets by name and/or schedule."""
        out = self.targets
        if name is not None:
            out = [t for t in out if t.name == name]
        if schedule is not None:
            out = [t for t in out if t.schedule is schedule]
        return list(out)
