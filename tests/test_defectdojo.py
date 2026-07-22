import urllib.error

from dastgate import defectdojo
from dastgate.defectdojo import DefectDojoConfig, build_form_fields, upload_report


class _FakeResponse:
    def __init__(self, status: int, body: bytes = b"{}"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeOpener:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.opened = None

    def open(self, request, timeout=None):
        self.opened = request
        if self._exc:
            raise self._exc
        return self._response


def _cfg(**kw):
    return DefectDojoConfig(base_url="https://dd.example.com", token="t", product_name="svc", **kw)


def test_reimport_endpoint_default():
    assert _cfg().endpoint_url().endswith("/api/v2/reimport-scan/")
    assert _cfg(reimport=False).endpoint_url().endswith("/api/v2/import-scan/")


def test_form_fields_scan_type_is_zap():
    fields = build_form_fields(_cfg())
    assert fields["scan_type"] == "ZAP Scan"
    assert fields["product_name"] == "svc"
    assert fields["product_type_name"] == "DAST"
    assert fields["close_old_findings"] == "true"


def test_upload_ok(tmp_path):
    report = tmp_path / "zap-report.xml"
    report.write_bytes(b"<OWASPZAPReport/>")
    opener = _FakeOpener(_FakeResponse(201, b'{"test_id": 42}'))
    result = upload_report(_cfg(), report, opener=opener)
    assert result.ok and result.status == 201
    assert result.url == "https://dd.example.com/test/42"
    assert opener.opened.full_url.endswith("/reimport-scan/")
    assert b'name="scan_type"' in opener.opened.data
    assert b"ZAP Scan" in opener.opened.data


def test_upload_failure_is_isolated(tmp_path):
    report = tmp_path / "r.xml"
    report.write_bytes(b"<x/>")
    opener = _FakeOpener(exc=urllib.error.URLError("boom"))
    result = upload_report(_cfg(), report, opener=opener)  # must NOT raise
    assert result.ok is False
    assert "connection error" in result.message


def test_upload_missing_config(tmp_path):
    report = tmp_path / "r.xml"
    report.write_bytes(b"<x/>")
    result = upload_report(DefectDojoConfig(base_url="", token=""), report)
    assert result.ok is False
    assert "not configured" in result.message


def test_upload_missing_file():
    result = upload_report(_cfg(), "/nope/missing.xml")
    assert result.ok is False
    assert "not found" in result.message


def test_test_url_parsing():
    assert defectdojo.test_url("https://dd", None) is None
    assert defectdojo.test_url("https://dd", {"nope": 1}) is None
    assert defectdojo.test_url("https://dd/", {"test": 7}) == "https://dd/test/7"
    assert defectdojo.test_url("https://dd", {"test_id": "9"}) == "https://dd/test/9"
