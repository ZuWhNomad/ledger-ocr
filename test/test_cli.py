import json
import os

from conftest import FIXTURES
from ledger_ocr import cli


def test_health_reports_engines(capsys):
    assert cli.main(["--health"]) == 0
    assert "ocr_engines" in json.loads(capsys.readouterr().out)


def test_json_result_and_exit_codes(tmp_path, capsys):
    sample = os.path.join(FIXTURES, "bank_statement.pdf")
    assert cli.main([sample, "--out", str(tmp_path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and len(out["rows"]) == 15 and os.path.exists(out["outputs"]["csv"])
    assert cli.main([str(tmp_path / "missing.pdf"), "--out", str(tmp_path)]) == 1
