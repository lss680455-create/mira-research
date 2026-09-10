"""evidence-log.csv 契约测试：版本识别、结构层/业务层规则。"""

import csv
import json

import pytest

from mira import evidence as ev


def write_log(tmp_path, header, rows, name="evidence-log.csv"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def canonical_row(**overrides):
    row = {column: "x" for column in ev.CANONICAL_COLUMNS_V12}
    row.update(
        {
            "source_id": "row-1",
            "claim_area": "business_model",
            "claim_type": "fact",
            "claim_text": "claim",
            "source_speaker": "SEC filing",
            "verification_status": "verified",
            "authority_level": "L1",
            "source_date": "2026-01-29",
            "as_of_date": "2026-04-14",
            "url_or_path": "https://example.com/a",
            "used_by_agent": "agent",
            "used_by_skill": "skill",
            "confidence": "high",
            "upstream_sources": "not_applicable",
            "notes": "notes",
            "evidence_category": "verified_fact",
            "freshness_status": "current",
            "conflict_status": "none",
            "treatment": "use_normally",
            "readiness_impact": "supports_durable_conclusion",
            "source_language": "en",
            "translation_basis": "not_translated",
        }
    )
    row.update(overrides)
    return [row[column] for column in ev.CANONICAL_COLUMNS_V12]


def errors_of(issues):
    return [issue for issue in issues if issue.level == "error"]


# ---------------------------------------------------------------- 读取与版本

def test_read_example_log(case_dir):
    log = ev.read_log(case_dir / "evidence-log.csv")
    assert log.version == "v1.2"
    assert log.is_canonical
    assert len(log.rows) == 9


def test_example_log_has_no_errors(case_dir, schemas_dir):
    log = ev.read_log(case_dir / "evidence-log.csv")
    assert errors_of(ev.validate_log(log, schemas_dir)) == []


def test_example_rows_convert_to_records(case_dir):
    log = ev.read_log(case_dir / "evidence-log.csv")
    records = [record for _, record in ev.rows_as_records(log)]
    assert len(records) == 9
    assert records[0]["source"]["authority_level"] == "L1"
    assert records[0]["source"]["source_language"] == "en"


def test_legacy_v11_header_detected(tmp_path):
    header = list(ev.CANONICAL_COLUMNS_V12)
    header.remove("source_language")
    header.remove("translation_basis")
    path = write_log(tmp_path, header, [["x"] * len(header)])
    log = ev.read_log(path)
    assert log.version == "v1.1"
    issues = ev.validate_log(log, None)
    assert any(issue.field == "version" and issue.level == "warn" for issue in issues)


def test_legacy_v1_header_detected(tmp_path):
    header = list(ev.CANONICAL_COLUMNS_V12)[:15]
    path = write_log(tmp_path, header, [["x"] * 15])
    log = ev.read_log(path)
    assert log.version == "v1"
    assert not log.is_canonical


def test_unknown_header_rejected(tmp_path):
    path = write_log(tmp_path, ["a", "b"], [["1", "2"]])
    with pytest.raises(ValueError):
        ev.read_log(path)


# ---------------------------------------------------------------- 结构层

def test_empty_required_field_is_error(tmp_path, schemas_dir):
    path = write_log(tmp_path, list(ev.CANONICAL_COLUMNS_V12), [canonical_row(claim_text="")])
    log = ev.read_log(path)
    issues = errors_of(ev.validate_log(log, schemas_dir))
    assert any(issue.field == "claim_text" and issue.row == 2 for issue in issues)


def test_bad_date_is_error(tmp_path, schemas_dir):
    path = write_log(tmp_path, list(ev.CANONICAL_COLUMNS_V12), [canonical_row(source_date="14/04/2026")])
    log = ev.read_log(path)
    issues = errors_of(ev.validate_log(log, schemas_dir))
    assert any(issue.field == "source_date" for issue in issues)


def test_bad_enum_is_error(tmp_path, schemas_dir):
    path = write_log(tmp_path, list(ev.CANONICAL_COLUMNS_V12), [canonical_row(claim_type="vibes")])
    log = ev.read_log(path)
    issues = errors_of(ev.validate_log(log, schemas_dir))
    assert any(issue.field == "claim_type" for issue in issues)


def test_row_width_mismatch_is_error(tmp_path, schemas_dir):
    path = tmp_path / "evidence-log.csv"
    path.write_text(
        ",".join(ev.CANONICAL_COLUMNS_V12) + "\n1,2,3\n",
        encoding="utf-8",
    )
    log = ev.read_log(path)
    issues = errors_of(ev.validate_log(log, schemas_dir))
    assert any(issue.field == "(row)" for issue in issues)


# ---------------------------------------------------------------- 业务层

def test_rumor_signal_high_confidence_rejected(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(claim_type="rumor_signal", confidence="high")],
    )
    issues = errors_of(ev.validate_log(ev.read_log(path), schemas_dir))
    assert any(issue.field == "confidence" for issue in issues)


def test_derived_row_requires_upstream_sources(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(claim_type="derived_calculation", upstream_sources="not_applicable")],
    )
    issues = errors_of(ev.validate_log(ev.read_log(path), schemas_dir))
    assert any(issue.field == "upstream_sources" for issue in issues)


def test_l6_row_requires_upstream_sources(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(authority_level="L6", upstream_sources="")],
    )
    issues = errors_of(ev.validate_log(ev.read_log(path), schemas_dir))
    assert any(issue.field == "upstream_sources" for issue in issues)


def test_verified_fact_unverified_rejected(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(evidence_category="verified_fact", verification_status="unverified")],
    )
    issues = errors_of(ev.validate_log(ev.read_log(path), schemas_dir))
    assert any(issue.field == "evidence_category" for issue in issues)


def test_weak_signal_durable_conclusion_needs_note(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(evidence_category="weak_signal", readiness_impact="supports_durable_conclusion", notes="")],
    )
    issues = ev.validate_log(ev.read_log(path), schemas_dir)
    assert any(issue.field == "readiness_impact" and issue.level == "error" for issue in issues)

    path2 = write_log(
        tmp_path / "b",
        list(ev.CANONICAL_COLUMNS_V12),
        [
            canonical_row(
                evidence_category="weak_signal",
                readiness_impact="supports_durable_conclusion",
                notes="降级处理：仅监控",
            )
        ],
        name="evidence-log.csv",
    )
    issues2 = ev.validate_log(ev.read_log(path2), schemas_dir)
    assert any(issue.field == "readiness_impact" and issue.level == "warn" for issue in issues2)


def test_judgment_translation_needs_original_excerpt(tmp_path, schemas_dir):
    path = write_log(
        tmp_path,
        list(ev.CANONICAL_COLUMNS_V12),
        [canonical_row(claim_type="guidance", translation_basis="mira_translation", notes="无原文片段")],
    )
    issues = ev.validate_log(ev.read_log(path), schemas_dir)
    assert any(issue.field == "notes" and issue.level == "warn" for issue in issues)


# ---------------------------------------------------------------- 统计

def test_stats_shape(case_dir):
    log = ev.read_log(case_dir / "evidence-log.csv")
    summary = ev.stats(log)
    assert summary["total"] == 9
    assert summary["version"] == "v1.2"
    assert sum(summary["by_category"].values()) == 9
    assert sum(summary["by_freshness"].values()) == 9
    assert summary["by_freshness"].get("stale") == 1
    assert len(summary["stale_rows"]) == 1
    assert len(summary["blocking_rows"]) == 1


def test_rows_as_records_validate_against_schema(case_dir, schemas_dir):
    from mira import contracts

    log = ev.read_log(case_dir / "evidence-log.csv")
    for _, record in ev.rows_as_records(log):
        assert contracts.validate_artifact(schemas_dir, "evidence", record) == []
