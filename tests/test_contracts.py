"""契约层测试：schema 自检、类型识别、单文件与包级校验。"""

import json
import shutil

import pytest

from mira import contracts

DATASETS = [
    ("thesis-card.yaml", "thesis-card"),
    ("routing.json", "routing"),
    ("refresh.yaml", "refresh"),
    ("monitoring.json", "monitoring"),
    ("research-package.json", "research-package"),
    ("refresh-report.json", "refresh"),
]


def test_schemas_selfcheck_clean(schemas_dir):
    assert contracts.validate_schemas_selfcheck(schemas_dir) == []


def test_schema_files_present(schemas_dir):
    expected = {
        "vocab.json",
        "thesis-card.schema.json",
        "evidence.schema.json",
        "refresh.schema.json",
        "monitoring.schema.json",
        "routing.schema.json",
        "research-package.schema.json",
    }
    assert {p.name for p in schemas_dir.glob("*.json")} == expected


def test_detect_kind(case_dir):
    for name, kind in DATASETS:
        path = case_dir / name
        data = contracts.load_document(path)
        assert contracts.detect_kind(path, data) == kind, name


def test_check_document_all_green(case_dir, schemas_dir):
    for name, kind in DATASETS:
        check = contracts.check_document(case_dir / name, schemas_dir)
        assert check.ok, (name, [e.render() for e in check.errors])
        assert check.kind == kind


def test_check_evidence_csv_green(case_dir, schemas_dir):
    check = contracts.check_evidence_csv(case_dir / "evidence-log.csv", schemas_dir)
    assert check.ok, [e.render() for e in check.errors]
    assert check.kind == "evidence-log"
    assert any("9" in note for note in check.notes)


def test_package_dir_all_green(case_dir, schemas_dir):
    checks = contracts.check_package_dir(case_dir, schemas_dir)
    kinds = {c.kind for c in checks}
    assert {"thesis-card", "routing", "refresh", "monitoring", "research-package", "evidence-log"} <= kinds
    for check in checks:
        assert check.ok, (check.path, [e.render() for e in check.errors])


def test_package_dir_flags_missing_artifact(case_dir, schemas_dir, tmp_path):
    target = tmp_path / "case"
    shutil.copytree(case_dir, target)
    (target / "refresh-report.md").unlink()
    (target / "report.md").unlink()
    checks = contracts.check_package_dir(target, schemas_dir)
    failures = [c for c in checks if not c.ok]
    assert failures, "manifest 声明的产物缺失时应报告失败"
    assert any("refresh-report.md" in c.path or any("refresh-report.md" in e.message for e in c.errors) for c in failures)


def test_check_document_bad_enum(tmp_path, schemas_dir):
    data = {
        "schema_version": "1.0",
        "interaction_mode": "routed_research",
        "primary_intent": "x",
        "task_mode": "first_pass_research",
        "research_object": "single_equity",
        "market_scope": "US equities",
        "time_boundary": "12 months",
        "depth_mode": "banana",
        "routing_basis": "x",
        "followup_prompt_mode": "standard",
        "followup_questions": ["a"],
    }
    path = tmp_path / "routing.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    check = contracts.check_document(path, schemas_dir)
    assert not check.ok
    assert any(error.path.endswith("depth_mode") for error in check.errors)


def test_scan_targets_directory(case_dir, schemas_dir):
    checks = contracts.scan_targets(case_dir, schemas_dir)
    kinds = {c.kind for c in checks}
    assert "evidence-log" in kinds
    assert all(c.ok for c in checks)


def test_load_document_unknown_suffix(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(contracts.UnsupportedDocument if hasattr(contracts, "UnsupportedDocument") else ValueError):
        contracts.load_document(path)
