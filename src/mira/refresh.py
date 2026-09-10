"""刷新引擎：把『过期』变成可计算、可复述、可排期的动作。

输入是 thesis-card 的 ``refresh`` 块与可选 refresh 计划（``refresh.yaml``），
输出 :class:`RefreshReport`：状态（fresh / due_soon / expired / unknown）、
距时间边界的余量、每个触发条件的核对结果与下一步动作清单。

状态规则（写死在契约里，保证可测）：

* 时间边界：``stale_after - as_of`` < 0 → expired；<= ``due_soon_days`` → due_soon；
  否则 fresh；
* 事件边界：任一 trigger ``fired`` → 整体至少 expired；``pending`` 且
  ``next_check`` 已到 → 整体至少 due_soon；
* 合并取最严重值；两个来源都没有信息时 → unknown。
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import evidence as ev

#: 严重度排序（数值越大越严重）。
SEVERITY = {"fresh": 0, "unknown": 1, "due_soon": 2, "expired": 3}


def _parse_date(text: Optional[str]) -> Optional[dt.date]:
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def time_status(as_of: dt.date, stale_after: Optional[dt.date], due_soon_days: int) -> str:
    """仅按时间边界计算状态。"""
    if stale_after is None:
        return "unknown"
    remaining = (stale_after - as_of).days
    if remaining < 0:
        return "expired"
    if remaining <= due_soon_days:
        return "due_soon"
    return "fresh"


@dataclass
class TriggerView:
    """单个触发条件的核对视图。"""

    trigger_id: str
    kind: str
    condition: str
    status: str
    next_check: Optional[str]
    last_checked: Optional[str]
    action_if_fired: Optional[str]
    overdue: bool  # pending 且 next_check 已到（含当天）

    def derived_status(self) -> Optional[str]:
        """触发条件对整体状态的贡献。"""
        if self.status == "fired":
            return "expired"
        if self.status == "pending" and self.overdue:
            return "due_soon"
        return None


@dataclass
class RefreshReport:
    """一次刷新计算的完整结果。"""

    thesis_id: str
    title: Optional[str]
    as_of: str
    stale_after: Optional[str]
    computed_status: str
    declared_status: Optional[str]
    status_source: str
    days_to_stale: Optional[int]
    due_soon_days: int
    triggers: List[TriggerView] = field(default_factory=list)
    must_refresh_if: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    evidence_summary: Optional[Dict[str, Any]] = None
    stale_evidence_rows: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 友好的 dict（供 --format json）。"""
        return {
            "schema_version": "1.0",
            "thesis_id": self.thesis_id,
            "title": self.title,
            "as_of": self.as_of,
            "stale_after": self.stale_after,
            "refresh_status": self.computed_status,
            "declared_status": self.declared_status,
            "status_source": self.status_source,
            "days_to_stale": self.days_to_stale,
            "due_soon_days": self.due_soon_days,
            "triggers": [t.__dict__ for t in self.triggers],
            "must_refresh_if": self.must_refresh_if,
            "next_actions": self.next_actions,
            "evidence_summary": self.evidence_summary,
            "stale_evidence_rows": self.stale_evidence_rows,
            "notes": self.notes,
        }


def build_refresh_report(
    card: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
    log: Optional[ev.EvidenceLog],
    *,
    as_of: dt.date,
    due_soon_days: int = 30,
) -> RefreshReport:
    """由论点卡 + 刷新计划 + 证据日志构建刷新报告。"""
    plan = plan or {}
    refresh_block = card.get("refresh") or {}

    stale_after_text = plan.get("stale_after") or refresh_block.get("stale_after")
    stale_after = _parse_date(stale_after_text)
    declared = plan.get("refresh_status")

    triggers: List[TriggerView] = []
    for raw in plan.get("triggers") or []:
        next_check = _parse_date(raw.get("next_check"))
        overdue = bool(
            raw.get("status") == "pending" and next_check is not None and next_check <= as_of
        )
        triggers.append(
            TriggerView(
                trigger_id=str(raw.get("trigger_id", "?")),
                kind=str(raw.get("kind", "?")),
                condition=str(raw.get("condition", "")),
                status=str(raw.get("status", "unknown")),
                next_check=raw.get("next_check"),
                last_checked=raw.get("last_checked"),
                action_if_fired=raw.get("action_if_fired"),
                overdue=overdue,
            )
        )

    candidates = [time_status(as_of, stale_after, due_soon_days)]
    candidates.extend(t.derived_status() for t in triggers)
    final = "fresh"
    for candidate in candidates:
        if candidate is None:
            continue
        if SEVERITY[candidate] > SEVERITY[final]:
            final = candidate

    sources: List[str] = []
    if time_status(as_of, stale_after, due_soon_days) != "fresh":
        sources.append("时间边界")
    if any(t.status == "fired" for t in triggers):
        sources.append("已触发事件")
    if any(t.overdue for t in triggers):
        sources.append("到期未核对")
    status_source = "+".join(sources) if sources else "全部条件未触发"

    evidence_summary = None
    stale_evidence_rows: List[str] = []
    if log is not None:
        evidence_summary = ev.stats(log)
        for row in evidence_summary.get("stale_rows", []):
            stale_evidence_rows.append(
                f"{row.get('source_id', '?')}（{row.get('claim_text', '')[:40]}…）"
            )
        if stale_evidence_rows and final == "fresh":
            final = "due_soon"
            status_source = (status_source + "+证据过期").lstrip("+")

    must_refresh_if = list(plan.get("must_refresh_if") or refresh_block.get("must_refresh_if") or [])

    actions: List[str] = []
    if final == "expired":
        if stale_after is not None and stale_after < as_of:
            actions.append(f"时间边界已过（stale_after={stale_after_text}）：先用最新数据复核再引用本结论")
        for trigger in triggers:
            if trigger.status == "fired":
                actions.append(f"处理已触发条件 {trigger.trigger_id}：{trigger.action_if_fired or trigger.condition}")
        for trigger in triggers:
            if trigger.overdue and trigger.status != "fired":
                actions.append(f"补做到期核对 {trigger.trigger_id}（next_check={trigger.next_check}）")
    elif final == "due_soon":
        if stale_after is not None:
            remaining = (stale_after - as_of).days
            if remaining >= 0:
                actions.append(f"排期刷新：距 stale_after 还有 {remaining} 天（{stale_after_text}）")
            else:
                actions.append(f"排期刷新：stale_after 已过（{stale_after_text}）")
        for trigger in triggers:
            if trigger.overdue:
                actions.append(f"补做到期核对 {trigger.trigger_id}（next_check={trigger.next_check}）")
    if stale_evidence_rows:
        actions.append("更新已过期证据行：" + "；".join(stale_evidence_rows))
    for trigger in triggers:
        if trigger.status == "pending" and not trigger.overdue and trigger.next_check:
            actions.append(f"按计划核对 {trigger.trigger_id}（next_check={trigger.next_check}）")
    if not actions:
        actions.append("无需动作：全部触发条件未触发且在有效期内")

    return RefreshReport(
        thesis_id=str(card.get("thesis_id") or plan.get("thesis_id") or "?"),
        title=card.get("title"),
        as_of=as_of.isoformat(),
        stale_after=stale_after_text,
        computed_status=final,
        declared_status=declared,
        status_source=status_source,
        days_to_stale=None if stale_after is None else (stale_after - as_of).days,
        due_soon_days=due_soon_days,
        triggers=triggers,
        must_refresh_if=must_refresh_if,
        next_actions=actions,
        evidence_summary=evidence_summary,
        stale_evidence_rows=stale_evidence_rows,
        notes=plan.get("notes") or card.get("notes"),
    )


_STATUS_ZH = {"fresh": "新鲜（fresh）", "due_soon": "临近过期（due_soon）", "expired": "已过期（expired）", "unknown": "未知（unknown）"}


def render_markdown(report: RefreshReport) -> str:
    """把刷新报告渲染为 Markdown。"""
    lines: List[str] = []
    lines.append(f"# 刷新报告 · {report.title or report.thesis_id}")
    lines.append("")
    lines.append(f"- thesis_id: `{report.thesis_id}`")
    lines.append(f"- as_of: {report.as_of}")
    lines.append(f"- stale_after: {report.stale_after or '（未设置）'}")
    lines.append(f"- 计算状态: {_STATUS_ZH.get(report.computed_status, report.computed_status)}（来源：{report.status_source}）")
    if report.declared_status:
        lines.append(f"- 计划声明状态: {report.declared_status}（以计算状态为准）")
    if report.days_to_stale is not None:
        if report.days_to_stale >= 0:
            lines.append(f"- 距时间边界: 还有 {report.days_to_stale} 天")
        else:
            lines.append(f"- 距时间边界: 已超出 {abs(report.days_to_stale)} 天")
    lines.append(f"- due_soon 判定窗口: 到期前 {report.due_soon_days} 天")
    lines.append("")

    lines.append("## 触发条件核对")
    lines.append("")
    if report.triggers:
        lines.append("| 条件 | 类型 | 状态 | 下次核对 | 触发条件 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for t in report.triggers:
            state = t.status
            if t.overdue and t.status == "pending":
                state += "（已到期待核对）"
            lines.append(
                f"| {t.trigger_id} | {t.kind} | {state} | {t.next_check or '—'} | {t.condition} |"
            )
    else:
        lines.append("（无触发条件）")
    lines.append("")

    lines.append("## 必须刷新的条件")
    lines.append("")
    for item in report.must_refresh_if:
        lines.append(f"- {item}")
    if not report.must_refresh_if:
        lines.append("（未定义）")
    lines.append("")

    if report.evidence_summary:
        summary = report.evidence_summary
        lines.append("## 证据面速览")
        lines.append("")
        lines.append(f"- 行数: {summary.get('total', 0)}（表头版本 {summary.get('version')}）")
        freshness = "，".join(f"{k}×{v}" for k, v in (summary.get("by_freshness") or {}).items())
        lines.append(f"- 新鲜度分布: {freshness or '—'}")
        if report.stale_evidence_rows:
            lines.append(f"- 过期行: {'；'.join(report.stale_evidence_rows)}")
        lines.append("")

    lines.append("## 下一步动作")
    lines.append("")
    for action in report.next_actions:
        lines.append(f"- [ ] {action}")
    lines.append("")

    if report.notes:
        lines.append("## 说明")
        lines.append("")
        lines.append(report.notes)
        lines.append("")

    return "\n".join(lines)


def render_json(report: RefreshReport) -> str:
    """把刷新报告渲染为 JSON 文本（键序稳定）。"""
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def load_plan(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """读取 refresh.yaml / refresh.json；不存在返回 None。"""
    if path is None or not Path(path).exists():
        return None
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore

        return yaml.safe_load(text)
    return json.loads(text)


def find_case_files(case_dir: Path) -> Dict[str, Optional[Path]]:
    """在 case 目录里定位论点卡 / 刷新计划 / 证据日志。"""
    def first(*names: str) -> Optional[Path]:
        for name in names:
            candidate = case_dir / name
            if candidate.exists():
                return candidate
        return None

    return {
        "card": first("thesis-card.yaml", "thesis-card.yml", "thesis-card.json"),
        "plan": first("refresh.yaml", "refresh.yml", "refresh.json"),
        "evidence": first("evidence-log.csv"),
    }
