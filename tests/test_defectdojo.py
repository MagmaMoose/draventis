from __future__ import annotations

import io
import urllib.error

from draventis import defectdojo


def test_build_multipart_contains_fields_and_file():
    body = defectdojo.build_multipart(
        fields={"scan_type": "ZAP Scan", "product_name": "example/app"},
        file_field="file",
        filename="zap.xml",
        file_bytes=b"<report/>",
        content_type="text/xml",
        boundary="BOUND",
    )
    text = body.decode("utf-8")
    assert "--BOUND" in text
    assert 'name="scan_type"' in text
    assert "ZAP Scan" in text
    assert 'filename="zap.xml"' in text
    assert "Content-Type: text/xml" in text
    assert "<report/>" in text
    assert text.rstrip().endswith("--BOUND--")


class _FakeResp:
    status = 201

    def read(self):
        return b'{"test_id": 42}'

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _OkOpener:
    def open(self, request, timeout=0):
        assert request.get_header("Authorization") == "Token secret"
        # A real User-Agent must be set (urllib's default is WAF-banned).
        assert request.get_header("User-agent", "").startswith("draventis/")  # nosec B101
        return _FakeResp()


def test_reimport_success_sets_test_link(tmp_path):
    report = tmp_path / "zap.xml"
    report.write_bytes(b"<report/>")
    result = defectdojo.reimport(
        base_url="https://dojo.example.com/",
        token="secret",
        scan_type="ZAP Scan",
        report_path=report,
        product_name="example/app",
        engagement_name="DAST - app",
        test_title="ZAP Scan",
        tags=["dast", "zap"],
        opener=_OkOpener(),
    )
    assert result.ok is True
    assert result.status == 201
    assert result.url == "https://dojo.example.com/test/42"


class _HttpErrorOpener:
    def __init__(self, body=b""):
        self._body = body

    def open(self, request, timeout=0):
        fp = io.BytesIO(self._body) if self._body else None
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, fp)


def test_reimport_http_error_is_isolated(tmp_path):
    report = tmp_path / "zap.xml"
    report.write_bytes(b"<report/>")
    result = defectdojo.reimport(
        base_url="https://dojo.example.com",
        token="secret",
        scan_type="ZAP Scan",
        report_path=report,
        product_name="p",
        engagement_name="e",
        test_title="ZAP Scan",
        opener=_HttpErrorOpener(),
    )
    assert result.ok is False
    assert result.status == 400


def test_reimport_http_error_surfaces_response_body(tmp_path):
    # DefectDojo's real validation message lives in the response body, not the
    # reason phrase.
    report = tmp_path / "zap.xml"
    report.write_bytes(b"<report/>")
    result = defectdojo.reimport(
        base_url="https://dojo.example.com",
        token="secret",
        scan_type="Bogus Scan",
        report_path=report,
        product_name="p",
        engagement_name="e",
        test_title="ZAP Scan",
        opener=_HttpErrorOpener(body=b'{"scan_type": ["Select a valid choice."]}'),
    )
    assert result.ok is False
    assert "Select a valid choice" in (result.error or "")


def test_reimport_missing_report_is_isolated(tmp_path):
    result = defectdojo.reimport(
        base_url="https://dojo.example.com",
        token="secret",
        scan_type="ZAP Scan",
        report_path=tmp_path / "does-not-exist.xml",
        product_name="p",
        engagement_name="e",
        test_title="ZAP Scan",
        opener=_OkOpener(),
    )
    assert result.ok is False
    assert "cannot read report" in (result.error or "")
