import textwrap

from dastgate.config import defectdojo_config_for, load_targets
from dastgate.model import Target


def test_load_targets_filters_and_defaults(tmp_path):
    p = tmp_path / "targets.yaml"
    p.write_text(
        textwrap.dedent(
            """
            targets:
              - name: a
                url: https://a.magmamoose.com
              - name: b
                url: https://b.magmamoose.com
                enabled: false
              - name: no-url
              - not-a-dict
              - url: https://no-name.example.com
            """
        )
    )
    targets = load_targets(p)
    assert [t.name for t in targets] == ["a"]
    assert targets[0].plan == "zap-baseline"
    assert targets[0].engagement == "DAST"
    assert targets[0].enabled is True


def test_load_targets_empty_file(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_targets(p) == []


def test_defectdojo_config_from_env(monkeypatch):
    monkeypatch.setenv("DEFECTDOJO_URL", "https://dd.magmamoose.com/")
    monkeypatch.setenv("DEFECTDOJO_TOKEN", "tok")
    monkeypatch.setenv("DD_PRODUCT_TYPE", "DAST")
    cfg = defectdojo_config_for(Target(name="svc", url="https://svc"))
    assert cfg.base_url == "https://dd.magmamoose.com"
    assert cfg.token == "tok"
    assert cfg.product_name == "svc"
    assert cfg.scan_type == "ZAP Scan"
    assert cfg.reimport is True


def test_defectdojo_config_insecure_flag(monkeypatch):
    monkeypatch.setenv("DEFECTDOJO_URL", "https://dd")
    monkeypatch.setenv("DEFECTDOJO_TOKEN", "t")
    monkeypatch.setenv("DD_INSECURE", "true")
    assert defectdojo_config_for(Target(name="s", url="u")).verify_ssl is False
