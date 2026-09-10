"""CLI 端到端测试：init / validate / refresh / report 子命令。"""

import json
import shutil

import pytest

from mira.cli import main


def run(capsys, argv):
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "1.0.0" in capsys.readouterr().out


def test_validate_all_green(capsys):
    code, out, _ = run(capsys, ["validate", "--all"])
    assert code == 0
    assert "失败 0" in out


def test_validate_json_summary(capsys):
    code, out, _ = run(capsys, ["validate", "--all", "--json"])
    assert code == 0
    payload = json.loads(out)
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["total"] == 7


def test_validate_missing_target(capsys):
    code, out, err = run(capsys, ["validate", "no/such/path-xyz"])
    assert code != 0
    assert "path-xyz" in (out + err)  # 路径不存在且逐条给出失败原因为终判


def test_validate_single_case(capsys, case_dir):
    code, out, _ = run(capsys, ["validate", str(case_dir)])
    assert code == 0
    assert "evidence-log.csv" in out


def test_init_roundtrip(capsys, tmp_path):
    dest = tmp_path / "nvda-2026-09"
    code, out, _ = run(
        capsys,
        ["init", str(dest), "--thesis-id", "nvda-2026-09", "--as-of", "2026-09-10"],
    )
    assert code == 0
    assert (dest / "thesis-card.yaml").exists()
    assert (dest / "refresh.yaml").exists()
    code, out, _ = run(capsys, ["validate", str(dest)])
    assert code == 0, out  # 脚手架出生即通过契约校验


def test_init_json_mode(capsys, tmp_path):
    dest = tmp_path / "tsla-2026-09"
    code, out, _ = run(
        capsys, ["init", str(dest), "--thesis-id", "tsla-2026-09", "--json", "--as-of", "2026-09-10"]
    )
    assert code == 0
    assert (dest / "thesis-card.json").exists()
    code, out, _ = run(capsys, ["validate", str(dest)])
    assert code == 0, out


def test_refresh_json_stdout(capsys, case_dir):
    code, out, _ = run(capsys, ["refresh", str(case_dir), "--as-of", "2026-09-10", "--format", "json"])
    assert code == 0
    payload = json.loads(out)
    assert payload["refresh_status"] == "expired"
    assert payload["schema_version"] == "1.0"


def test_refresh_write_into_copy(capsys, case_dir, tmp_path):
    target = tmp_path / "case"
    shutil.copytree(case_dir, target)
    (target / "refresh-report.md").unlink()
    (target / "refresh-report.json").unlink()
    code, out, _ = run(capsys, ["refresh", str(target), "--as-of", "2026-09-10", "--write"])
    assert code == 0
    assert (target / "refresh-report.md").exists()
    assert (target / "refresh-report.json").exists()


def test_report_stdout(capsys, case_dir):
    code, out, _ = run(capsys, ["report", str(case_dir), "--as-of", "2026-09-10"])
    assert code == 0
    assert "aapl-2026-04" in out
    assert "过期" in out


def test_report_to_file(capsys, case_dir, tmp_path):
    dest = tmp_path / "report.md"
    code, out, _ = run(capsys, ["report", str(case_dir), "-o", str(dest), "--as-of", "2026-09-10"])
    assert code == 0
    assert dest.exists()
    assert "aapl-2026-04" in dest.read_text(encoding="utf-8")
