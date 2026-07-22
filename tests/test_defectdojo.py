from __future__ import annotations

import urllib.error

from dastgate import defectdojo


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

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _OkOpener:
    def open(self, request, timeout=0):
        assert request.get_header("Authorization") == "Token secret"
        return _FakeResp()


def test_reimport_success(tmp_path):
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


class _HttpErrorOpener:
    def open(self, request, timeout=0):
        raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, None)


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
    assert result.status == 500


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
