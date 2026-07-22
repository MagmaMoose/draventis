"""DefectDojo reimport client — first-class and failure-isolated.

Uploads a DAST scan report (ZAP XML by default) via DefectDojo's ``reimport-scan``
API so a nightly re-run updates one Test per engagement (``close_old_findings``
mitigates alerts that disappear). ``auto_create_context`` creates the
product/engagement/test on first run.

Stdlib only (urllib) — mirrors chargate's ``defectdojo.py``. By contract a
DefectDojo failure NEVER raises out of :func:`upload_report`; it returns a result
with ``ok=False`` so the caller can log-and-continue.
"""

from __future__ import annotations

import http.client
import json
import ssl
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dastgate import __version__

_BOUNDARY_PREFIX = "----dastgateDefectDojoBoundary7MA4YWxkTrZu0gW"
# Identify ourselves rather than the default "Python-urllib/X.Y", which edge WAFs
# (e.g. Cloudflare Bot Fight Mode / error 1010) commonly ban by client signature.
_USER_AGENT = f"dastgate/{__version__} (+https://github.com/MagmaMoose/dastgate)"


@dataclass(frozen=True)
class DefectDojoConfig:
    base_url: str
    token: str
    product_name: str | None = None
    product_type_name: str | None = "DAST"
    engagement_name: str | None = "DAST"
    engagement_id: int | None = None
    scan_type: str = "ZAP Scan"
    reimport: bool = True
    close_old_findings: bool = True
    auto_create_context: bool = True
    minimum_severity: str = "Info"
    active: bool = True
    verified: bool = False
    test_title: str | None = None
    tags: tuple[str, ...] = ()
    file_content_type: str = "application/xml"
    verify_ssl: bool = True
    timeout: float = 300.0

    def endpoint_url(self) -> str:
        path = "reimport-scan" if self.reimport else "import-scan"
        return f"{self.base_url.rstrip('/')}/api/v2/{path}/"


@dataclass(frozen=True)
class DefectDojoResult:
    ok: bool
    endpoint: str
    status: int | None = None
    message: str = ""
    response: dict[str, Any] | None = None
    url: str | None = None  # link to the imported Test in the DefectDojo UI


def _bool(value: bool) -> str:
    return "true" if value else "false"


def test_url(base_url: str, response: dict[str, Any] | None) -> str | None:
    """Build a UI link to the imported Test from an (re)import-scan response."""
    if not isinstance(response, dict):
        return None
    raw = response.get("test_id")
    if raw is None:
        raw = response.get("test")
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        return None
    test_id = str(raw).strip()
    if not test_id.isdigit():
        return None
    return f"{base_url.rstrip('/')}/test/{test_id}"


def build_form_fields(config: DefectDojoConfig) -> dict[str, str]:
    """The non-file form fields for the (re)import request."""
    fields: dict[str, str] = {
        "scan_type": config.scan_type,
        "active": _bool(config.active),
        "verified": _bool(config.verified),
        "close_old_findings": _bool(config.close_old_findings),
        "auto_create_context": _bool(config.auto_create_context),
        "minimum_severity": config.minimum_severity,
    }
    if config.product_type_name:
        # Required for auto_create_context to create a not-yet-existing product.
        fields["product_type_name"] = config.product_type_name
    if config.product_name:
        fields["product_name"] = config.product_name
    if config.engagement_name:
        fields["engagement_name"] = config.engagement_name
    if config.engagement_id is not None:
        fields["engagement"] = str(config.engagement_id)
    if config.test_title:
        fields["test_title"] = config.test_title
    if config.tags:
        fields["tags"] = ",".join(config.tags)
    return fields


def encode_multipart(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    content_type: str = "application/xml",
    boundary: str = _BOUNDARY_PREFIX,
) -> bytes:
    """Encode ``fields`` plus one file as a multipart/form-data body."""
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def build_request(config: DefectDojoConfig, report_path: Path) -> urllib.request.Request:
    boundary = f"{_BOUNDARY_PREFIX}{uuid.uuid4().hex}"
    body = encode_multipart(
        build_form_fields(config),
        file_field="file",
        filename=report_path.name,
        file_bytes=report_path.read_bytes(),
        content_type=config.file_content_type,
        boundary=boundary,
    )
    request = urllib.request.Request(config.endpoint_url(), data=body, method="POST")
    request.add_header("Authorization", f"Token {config.token}")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", _USER_AGENT)
    return request


def upload_report(
    config: DefectDojoConfig,
    report_path: str | Path,
    *,
    opener: urllib.request.OpenerDirector | None = None,
) -> DefectDojoResult:
    """Upload a DAST report to DefectDojo. Never raises — returns a result."""
    endpoint = config.endpoint_url()
    path = Path(report_path)
    if not config.base_url or not config.token:
        return DefectDojoResult(False, endpoint, message="DefectDojo URL/token not configured")
    if not path.is_file():
        return DefectDojoResult(False, endpoint, message=f"report file not found: {path}")

    try:
        request = build_request(config, path)
    except OSError as exc:
        return DefectDojoResult(False, endpoint, message=f"could not read report: {exc}")

    if opener is None:
        if config.verify_ssl:
            opener = urllib.request.build_opener()
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    try:
        with opener.open(request, timeout=config.timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            raw = response.read().decode("utf-8", errors="replace")
            parsed = _safe_json(raw)
            ok = 200 <= int(status) < 300
            return DefectDojoResult(
                ok=ok,
                endpoint=endpoint,
                status=int(status),
                message="uploaded" if ok else raw[:500],
                response=parsed,
                url=test_url(config.base_url, parsed) if ok else None,
            )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500] if exc.fp else ""
        return DefectDojoResult(
            False, endpoint, status=exc.code, message=f"HTTP {exc.code}: {detail}"
        )
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        # http.client.HTTPException (IncompleteRead/BadStatusLine) is NOT an OSError.
        return DefectDojoResult(False, endpoint, message=f"connection error: {exc}")


def _safe_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
