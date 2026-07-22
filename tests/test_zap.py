from dastgate.model import Target
from dastgate.zap import REPORT_FILE, render_plan, run_baseline


def test_render_plan_substitutes():
    out = render_plan(
        "url=${TARGET_URL} dir=${REPORT_DIR} f=${REPORT_FILE}",
        target_url="https://x",
        report_dir="/w",
    )
    assert out == "url=https://x dir=/w f=zap-report"


def test_render_plan_leaves_unknown_vars():
    # safe_substitute must not choke on ZAP's own ${OTHER} placeholders.
    assert render_plan("${OTHER}", target_url="u", report_dir="d") == "${OTHER}"


def test_run_baseline_produces_report(tmp_path):
    autodir = tmp_path / "automation"
    autodir.mkdir()
    (autodir / "zap-baseline.yaml").write_text("url: ${TARGET_URL}\nout: ${REPORT_DIR}\n")
    work = tmp_path / "work"
    calls: list[list[str]] = []

    def fake_runner(cmd):
        calls.append(cmd)
        (work / f"{REPORT_FILE}.xml").write_text("<OWASPZAPReport/>")  # simulate ZAP
        return None

    target = Target(name="svc", url="https://svc.magmamoose.com")
    report = run_baseline(target, automation_dir=autodir, work_dir=work, runner=fake_runner)

    assert report is not None and report.name == "zap-report.xml"
    assert calls and calls[0][0] == "zap.sh" and "-autorun" in calls[0]
    rendered = (work / "zap-baseline.rendered.yaml").read_text()
    assert "https://svc.magmamoose.com" in rendered


def test_run_baseline_no_report_returns_none(tmp_path):
    autodir = tmp_path / "automation"
    autodir.mkdir()
    (autodir / "zap-baseline.yaml").write_text("x: ${TARGET_URL}")
    report = run_baseline(
        Target(name="s", url="https://s"),
        automation_dir=autodir,
        work_dir=tmp_path / "w",
        runner=lambda cmd: None,  # runs but writes no report
    )
    assert report is None
