"""DefectDojo ``reimport-scan`` client.

Stdlib ``urllib`` only (no runtime deps) and *failure-isolated*: an upload error
is logged and swallowed so a transient DefectDojo problem never fails the scan.
Reimport (not import) is deliberate — DefectDojo dedupes against the existing
test, reactivates regressions, and with ``close_old_findings`` mitigates alerts
that disappeared, giving "what's new / fixed since last scan" without a
merge-base diff.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import __version__

_CRLF = b"\r\n"

# A real User-Agent: the urllib default ("Python-urllib/X.Y") is commonly banned
# by edge WAFs by client signature (e.g. Cloudflare Bot Fight Mode, error 1010),
# which would silently 403 every upload.
_USER_AGENT = f"draventis/{__version__} (+https://github.com/MagmaMoose/draventis)"


@dataclass(slots=True)
class ReimportResult:
    """Outcome of a single reimport attempt."""

    ok: bool
    status: int | None = None
    error: str | None = None
    url: str | None = None  # link to the imported DefectDojo Test, when parseable


def _test_url(base_url: str, body: bytes) -> str | None:
    """Build a link to the imported Test from the reimport response, if present."""
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    test_id = data.get("test_id") or data.get("test")
    if test_id is None:
        return None
    return f"{base_url.rstrip('/')}/test/{test_id}"


def build_multipart(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    content_type: str,
    boundary: str,
) -> bytes:
    """Assemble a ``multipart/form-data`` body (stdlib, deterministic for tests)."""
    parts: list[bytes] = []
    marker = f"--{boundary}".encode()
    for key, value in fields.items():
        parts += [
            marker,
            f'Content-Disposition: form-data; name="{key}"'.encode(),
            b"",
            str(value).encode("utf-8"),
        ]
    # Percent-encode CR/LF/" in the filename so it can't break out of the header
    # (WHATWG form-data behaviour). Inputs are trusted config today; this keeps it
    # robust if the report name ever derives from less-trusted data.
    safe_filename = filename.replace("\r", "%0D").replace("\n", "%0A").replace('"', "%22")
    parts += [
        marker,
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{safe_filename}"'
        ).encode(),
        f"Content-Type: {content_type}".encode(),
        b"",
        file_bytes,
        f"--{boundary}--".encode(),
        b"",
    ]
    return _CRLF.join(parts)


def _content_type_for(report_path: Path) -> str:
    suffix = report_path.suffix.lower()
    return {
        ".xml": "text/xml",
        ".json": "application/json",
        ".jsonl": "application/json",
        ".sarif": "application/json",
    }.get(suffix, "application/octet-stream")


def reimport(
    *,
    base_url: str,
    token: str,
    scan_type: str,
    report_path: str | Path,
    product_name: str,
    engagement_name: str,
    test_title: str,
    tags: list[str] | None = None,
    product_type: str | None = None,
    auto_create_context: bool = True,
    close_old_findings: bool = True,
    timeout: int = 300,
    opener: urllib.request.OpenerDirector | None = None,
) -> ReimportResult:
    """POST a scan report to ``/api/v2/reimport-scan/``.

    Never raises: on any error it returns ``ReimportResult(ok=False, ...)`` so the
    caller can log and carry on to the next target.
    """
    report = Path(report_path)
    try:
        file_bytes = report.read_bytes()
    except OSError as exc:
        return ReimportResult(ok=False, error=f"cannot read report {report}: {exc}")

    fields: dict[str, str] = {
        "scan_type": scan_type,
        "product_name": product_name,
        "engagement_name": engagement_name,
        "test_title": test_title,
        "auto_create_context": "true" if auto_create_context else "false",
        "close_old_findings": "true" if close_old_findings else "false",
        "active": "true",
        "verified": "false",
    }
    if product_type:
        fields["product_type_name"] = product_type
    if tags:
        fields["tags"] = ",".join(tags)

    boundary = uuid.uuid4().hex
    body = build_multipart(
        fields,
        file_field="file",
        filename=report.name,
        file_bytes=file_bytes,
        content_type=_content_type_for(report),
        boundary=boundary,
    )

    url = f"{base_url.rstrip('/')}/api/v2/reimport-scan/"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": _USER_AGENT,
        },
    )
    do_open = opener.open if opener is not None else urllib.request.urlopen
    try:
        with do_open(request, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            try:
                payload = resp.read()
            except Exception:
                payload = b""
            return ReimportResult(ok=True, status=status, url=_test_url(base_url, payload))
    except urllib.error.HTTPError as exc:
        # Surface DefectDojo's actual validation message (in the response body),
        # not just the generic reason phrase, so a failed nightly is diagnosable.
        detail = ""
        try:
            if exc.fp is not None:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        message = f"HTTP {exc.code}: {detail or exc.reason}"
        return ReimportResult(ok=False, status=exc.code, error=message)
    except Exception as exc:  # failure isolation is the whole point
        return ReimportResult(ok=False, error=str(exc))
