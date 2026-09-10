"""刷新引擎测试：时间边界、触发条件、报告渲染与契约一致性。"""

import datetime as dt
import json
import pathlib

import pytest

from mira import contracts, evidence as ev, refresh as rf


def load_document(path: pathlib.Path):
    return contracts.load_document(path)


@pytest.fixture()
def pieces(case_dir):
    card = load_document(case_dir / "thesis-card.yaml")
    plan = load_document(case_dir / "refresh.yaml")
    log = ev.read_log(case_dir / "evidence-log.csv")
    return card, plan, log


# ---------------------------------------------------------------- time_status

def test_time_status_boundaries():
    as_of = dt.date(2026, 9, 10)
    assert rf.time_status(as_of, None, 30) == "unknown"
    assert rf.time_status(as_of, dt.date(2026, 9, 9), 30) == "expired"
    assert rf.time_status(as_of, as_of, 30) == "due_soon"
    assert rf.time_status(as_of, as_of + dt.timedelta(days=30), 30) == "due_soon"
    assert rf.time_status(as_of, as_of + dt.timedelta(days=31), 30) == "fresh"


# ---------------------------------------------------------------- 示例包计算

def test_example_expired_as_of_demo_date(pieces):
    card, plan, log = pieces
    report = rf.build_refresh_report(card, plan, log, as_of=dt.date(2026, 9, 10))
    assert report.computed_status == "expired"
    assert report.declared_status == "fresh"  # 计划快照声明 fresh，计算状态覆盖它
    assert report.days_to_stale == -59
    assert report.status_source  # 非空：说明状态来自哪里
    assert report.stale_evidence_rows and all(
        row.startswith("derived_aapl_apr2026_thesis") for row in report.stale_evidence_rows
    )
    assert len(report.stale_evidence_rows) == 1
    assert report.next_actions  # 必须给出下一步动作
    overdue = [t.trigger_id for t in report.triggers if t.overdue]
    assert overdue == ["T1-time", "T3-price", "T4-policy"]


def test_example_plan_date_flags_stale_evidence(pieces):
    card, plan, log = pieces
    report = rf.build_refresh_report(card, plan, log, as_of=dt.date(2026, 4, 14))
    # 计划快照声明 fresh；但包里已有过期证据行 → 引擎至少报 due_soon
    assert report.declared_status == "fresh"
    assert report.computed_status == "due_soon"
    assert report.status_source.endswith("证据过期")
    assert report.days_to_stale == 90
    assert [t for t in report.triggers if t.overdue] == []


def test_fired_trigger_forces_expired():
    card = {"thesis_id": "t-1", "refresh": {"stale_after": "2099-01-01", "must_refresh_if": ["条件"]}}
    plan = {
        "triggers": [
            {"trigger_id": "T-x", "kind": "price", "condition": "跌破关键位", "status": "fired"},
        ],
        "must_refresh_if": ["条件"],
    }
    report = rf.build_refresh_report(card, plan, None, as_of=dt.date(2026, 9, 10))
    assert report.computed_status == "expired"
    assert any(t.trigger_id == "T-x" and t.status == "fired" for t in report.triggers)
    assert report.next_actions  # fired 必须产生下一步动作


def test_unknown_stale_after():
    card = {"thesis_id": "t-2", "refresh": {}}
    report = rf.build_refresh_report(card, None, None, as_of=dt.date(2026, 9, 10))
    assert report.computed_status == "unknown"


def test_due_soon_from_overdue_pending_trigger():
    card = {"thesis_id": "t-3", "refresh": {"stale_after": "2099-01-01", "must_refresh_if": ["x"]}}
    plan = {
        "triggers": [
            {"trigger_id": "T-y", "kind": "event", "condition": "c", "status": "pending", "next_check": "2026-09-01"},
        ]
    }
    report = rf.build_refresh_report(card, plan, None, as_of=dt.date(2026, 9, 10))
    assert report.computed_status == "due_soon"


# ---------------------------------------------------------------- 渲染

def test_render_markdown_contains_core_sections(pieces):
    card, plan, log = pieces
    report = rf.build_refresh_report(card, plan, log, as_of=dt.date(2026, 9, 10))
    text = rf.render_markdown(report)
    assert "# 刷新报告" in text
    assert "## 触发条件核对" in text
    assert "## 必须刷新的条件" in text
    assert "已超出 59 天" in text
    assert "T1-time" in text


def test_render_json_matches_refresh_schema(pieces, schemas_dir):
    card, plan, log = pieces
    report = rf.build_refresh_report(card, plan, log, as_of=dt.date(2026, 9, 10))
    payload = json.loads(rf.render_json(report))
    assert payload["schema_version"] == "1.0"
    assert payload["refresh_status"] == "expired"
    assert contracts.validate_artifact(schemas_dir, "refresh", payload) == []


def test_committed_refresh_report_is_valid(schemas_dir, case_dir):
    """仓库里提交的 refresh-report.json 必须满足刷新契约（防止样例漂移）。"""
    payload = json.loads((case_dir / "refresh-report.json").read_text(encoding="utf-8"))
    assert contracts.validate_artifact(schemas_dir, "refresh", payload) == []
    assert payload["refresh_status"] == "expired"


# ---------------------------------------------------------------- 文件定位

def test_find_case_files(case_dir):
    files = rf.find_case_files(case_dir)
    assert files["card"].name == "thesis-card.yaml"
    assert files["plan"].name == "refresh.yaml"
    assert files["evidence"].name == "evidence-log.csv"
