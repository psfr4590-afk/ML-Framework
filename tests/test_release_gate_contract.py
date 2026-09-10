import sys

import scripts.verify_release as verify_release


def test_release_gate_does_not_claim_native_prerequisites_without_bootstrap(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["verify_release.py"])
    monkeypatch.setattr(verify_release, "run", lambda cmd: 0)

    assert verify_release.main() == 0
    output = capsys.readouterr().out
    assert "required environment checks are green" in output
    assert "Native artifact verification was not run" in output


def test_release_gate_bootstrap_mode_reports_native_check(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["verify_release.py", "--bootstrap-native"])
    commands = []

    def fake_run(cmd):
        commands.append(cmd)
        return 0

    monkeypatch.setattr(verify_release, "run", fake_run)
    monkeypatch.setattr(verify_release, "_native_smoke", lambda: 0)

    assert verify_release.main() == 0
    output = capsys.readouterr().out
    assert "native export prerequisites are green" in output
    assert any("--ensure-llamacpp" in item for command in commands for item in command)
