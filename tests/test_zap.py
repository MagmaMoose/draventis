import yaml

from dastgate.model import Target
from dastgate.zap import REPORT_FILE, render_plan, run_baseline


def test_render_plan_substitutes_as_yaml_values():
    tmpl = (
        "env:\n"
        "  contexts:\n"
        '    - urls: ["${TARGET_URL}"]\n'
        "jobs:\n"
        "  - type: report\n"
        "    parameters:\n"
        '      reportDir: "${REPORT_DIR}"\n'
        '      reportFile: "${REPORT_FILE}"\n'
    )
    plan = yaml.safe_load(render_plan(tmpl, target_url="https://x.example.com", report_dir="/w"))
    assert plan["env"]["contexts"][0]["urls"] == ["https://x.example.com"]
    assert plan["jobs"][0]["parameters"]["reportDir"] == "/w"
    assert plan["jobs"][0]["parameters"]["reportFile"] == "zap-report"


def test_render_plan_escapes_scope_regex():
    plan = yaml.safe_load(
        render_plan('inc: ["${TARGET_SCOPE_REGEX}"]', target_url="https://a.b.com", report_dir="/w")
    )
    assert plan["inc"][0] == "https://a\\.b\\.com.*"  # dots escaped, ".*" appended


def test_render_plan_hostile_url_cannot_inject_yaml():
    evil = 'https://x"\njobs:\n  - type: activeScan'  # tries to break out + add a job
    plan = yaml.safe_load(
        render_plan('urls: ["${TARGET_URL}"]', target_url=evil, report_dir="/w")
    )
    assert plan["urls"] == [evil]  # preserved as one scalar
    assert list(plan.keys()) == ["urls"]  # no injected top-level job


def test_render_plan_leaves_unknown_tokens():
    plan = yaml.safe_load(render_plan('x: "${OTHER}"', target_url="u", report_dir="d"))
    assert plan["x"] == "${OTHER}"


def test_run_baseline_produces_report(tmp_path):
    autodir = tmp_path / "automation"
    autodir.mkdir()
    (autodir / "zap-baseline.yaml").write_text('url: "${TARGET_URL}"\nout: "${REPORT_DIR}"\n')
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
    rendered = yaml.safe_load((work / "zap-baseline.rendered.yaml").read_text())
    assert rendered["url"] == "https://svc.magmamoose.com"


def test_run_baseline_no_report_returns_none(tmp_path):
    autodir = tmp_path / "automation"
    autodir.mkdir()
    (autodir / "zap-baseline.yaml").write_text('x: "${TARGET_URL}"')
    report = run_baseline(
        Target(name="s", url="https://s"),
        automation_dir=autodir,
        work_dir=tmp_path / "w",
        runner=lambda cmd: None,
    )
    assert report is None
