"""研究包读出：把一个 case 目录汇总成一份可读、可对账的 Markdown / JSON。

``mira report <case_dir>`` 的渲染层。设计原则：

* 只陈述目录里实际存在的文件（缺失的产物在清单里明确标 ✗）；
* 数字全部来自 artifact 本体（evidence-log、manifest、refresh 计划），不做二次脑补；
* 输出对同一输入稳定（除 as_of 由调用方显式传入外，不含运行时间戳）。
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import evidence as ev
from . import refresh as rf


def _load_yaml_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore

        return yaml.safe_load(text)
    return json.loads(text)


@dataclass
class CaseReadout:
    """case 目录的读出结果（供渲染）。"""

    case_dir: str
    as_of: str
    manifest: Optional[Dict[str, Any]] = None
    card: Optional[Dict[str, Any]] = None
    routing: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None
    refresh: Optional[rf.RefreshReport] = None
    evidence_summary: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_dir": self.case_dir,
            "as_of": self.as_of,
            "manifest": self.manifest,
            "thesis_card": self.card,
            "routing": self.routing,
            "monitoring": self.monitoring,
            "refresh": self.refresh.to_dict() if self.refresh else None,
            "evidence_summary": self.evidence_summary,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
        }


def _safe_load(path: Optional[Path], warnings: List[str]) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return _load_yaml_json(path)
    except Exception as exc:  # pragma: no cover - 容错分支
        warnings.append(f"无法解析 {path.name}: {exc}")
        return None


def build_readout(case_dir: Path, *, as_of: dt.date, due_soon_days: int = 30) -> CaseReadout:
    """读取 case 目录并汇总为 :class:`CaseReadout`。"""
    warnings: List[str] = []
    manifest = _safe_load(
        next((p for p in (case_dir / "research-package.json", case_dir / "research-package-manifest.json") if p.exists()), None),
        warnings,
    )
    card = _safe_load(next((p for p in [case_dir / n for n in ("thesis-card.yaml", "thesis-card.yml", "thesis-card.json")] if p.exists()), None), warnings)
    routing = _safe_load(case_dir / "routing.json", warnings)
    monitoring = _safe_load(case_dir / "monitoring.json", warnings)
    plan = _safe_load(case_dir / "refresh.yaml", warnings) or _safe_load(case_dir / "refresh.json", warnings)

    log: Optional[ev.EvidenceLog] = None
    evidence_path = case_dir / "evidence-log.csv"
    if evidence_path.exists():
        try:
            log = ev.read_log(evidence_path)
        except Exception as exc:
            warnings.append(f"evidence-log.csv 无法读取: {exc}")

    refresh_report: Optional[rf.RefreshReport] = None
    if card is not None or plan is not None:
        refresh_report = rf.build_refresh_report(
            card or {}, plan, log, as_of=as_of, due_soon_days=due_soon_days
        )

    evidence_summary = ev.stats(log) if log is not None else None

    artifacts: List[Dict[str, Any]] = []
    if isinstance(manifest, dict):
        for rel in manifest.get("hero_artifacts", []) or []:
            artifacts.append({"path": rel, "role": "hero", "exists": (case_dir / rel).exists()})
        for rel in manifest.get("support_artifacts", []) or []:
            artifacts.append({"path": rel, "role": "support", "exists": (case_dir / rel).exists()})

    return CaseReadout(
        case_dir=str(case_dir),
        as_of=as_of.isoformat(),
        manifest=manifest,
        card=card,
        routing=routing,
        monitoring=monitoring,
        refresh=refresh_report,
        evidence_summary=evidence_summary,
        artifacts=artifacts,
        warnings=warnings,
    )


_STATUS_ZH = {
    "fresh": "新鲜",
    "due_soon": "临近过期",
    "expired": "已过期",
    "unknown": "未知",
}


def render_markdown(readout: CaseReadout) -> str:
    """渲染 case 读出为 Markdown。"""
    lines: List[str] = []
    manifest = readout.manifest or {}
    title = manifest.get("case_id") or Path(readout.case_dir).name
    lines.append(f"# 研究包读出 · {title}")
    lines.append("")
    lines.append(f"- 目录: `{readout.case_dir}`")
    lines.append(f"- as_of: {readout.as_of}")
    lines.append("")

    lines.append("## 包概览")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("| --- | --- |")
    for key, label in [
        ("research_object", "研究对象"),
        ("market_scope", "市场范围"),
        ("research_cutoff_date", "调研截止日"),
        ("package_type", "包类型"),
        ("readiness_level", "就绪度"),
        ("primary_workflow", "主工作流"),
        ("evidence_log_status", "证据表状态"),
        ("stale_after", "时间边界"),
    ]:
        if isinstance(manifest, dict) and manifest.get(key) is not None:
            lines.append(f"| {label} | {manifest.get(key)} |")
    lines.append("")

    if readout.artifacts:
        lines.append("## 产物清单")
        lines.append("")
        for artifact in readout.artifacts:
            mark = "✓" if artifact["exists"] else "✗"
            lines.append(f"- [{mark}] `{artifact['path']}`（{artifact['role']}）")
        lines.append("")

    card = readout.card
    if isinstance(card, dict):
        lines.append("## 论点状态")
        lines.append("")
        lines.append(f"- 状态: {card.get('state')}（置信度 {card.get('confidence')}）")
        lines.append(f"- 核心主张: {card.get('core_claim')}")
        variables = card.get("key_variables") or []
        if variables:
            lines.append("")
            lines.append("| 变量 | 共识锚点 | Mira 视角 | 定价程度 |")
            lines.append("| --- | --- | --- | --- |")
            for variable in variables:
                lines.append(
                    f"| {variable.get('variable')} | {variable.get('consensus_proxy')} | {variable.get('mira_view')} | {variable.get('price_in_status')} |"
                )
        lines.append("")

    if readout.evidence_summary:
        summary = readout.evidence_summary
        lines.append("## 证据面")
        lines.append("")
        lines.append(f"- 行数: {summary.get('total', 0)}（表头版本 {summary.get('version')}）")
        categories = "，".join(f"{k}×{v}" for k, v in (summary.get("by_category") or {}).items())
        treatments = "，".join(f"{k}×{v}" for k, v in (summary.get("by_treatment") or {}).items())
        lines.append(f"- 证据类别: {categories or '—'}")
        lines.append(f"- 处理方式: {treatments or '—'}")
        if summary.get("stale_rows"):
            lines.append(f"- 过期行: {len(summary['stale_rows'])} 条")
        if summary.get("blocking_rows"):
            lines.append(f"- 阻塞行: {len(summary['blocking_rows'])} 条")
        lines.append("")

    if readout.refresh is not None:
        report = readout.refresh
        lines.append("## 刷新状态")
        lines.append("")
        lines.append(
            f"- 计算状态: {_STATUS_ZH.get(report.computed_status, report.computed_status)}（来源：{report.status_source}）"
        )
        if report.days_to_stale is not None:
            if report.days_to_stale >= 0:
                lines.append(f"- 距时间边界: 还有 {report.days_to_stale} 天（stale_after={report.stale_after}）")
            else:
                lines.append(f"- 距时间边界: 已超出 {abs(report.days_to_stale)} 天（stale_after={report.stale_after}）")
        lines.append("")
        for action in report.next_actions:
            lines.append(f"- [ ] {action}")
        lines.append("")

    monitoring = readout.monitoring
    if isinstance(monitoring, dict):
        items = monitoring.get("items") or []
        lines.append("## 监控队列")
        lines.append("")
        if items:
            lines.append("| 变量 | 来源 | 频率 | 状态 | 升级条件 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for item in items:
                lines.append(
                    f"| {item.get('variable')} | {item.get('watch_source')} | {item.get('cadence')} | {item.get('status')} | {item.get('escalation_condition')} |"
                )
        else:
            lines.append("（队列为空）")
        lines.append("")

    routing = readout.routing
    if isinstance(routing, dict):
        lines.append("## 路由卡片")
        lines.append("")
        for key, label in [
            ("interaction_mode", "交互模式"),
            ("task_mode", "任务类型"),
            ("depth_mode", "深度"),
            ("decision_pressure", "决策压力"),
            ("quant_dependency", "计算依赖"),
            ("primary_workflow", "主工作流"),
        ]:
            if routing.get(key) is not None:
                lines.append(f"- {label}: {routing.get(key)}")
        questions = routing.get("followup_questions") or []
        if questions:
            lines.append("")
            lines.append("追问清单:")
            for question in questions:
                lines.append(f"- {question}")
        lines.append("")

    if readout.warnings:
        lines.append("## 警告")
        lines.append("")
        for warning in readout.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def render_json(readout: CaseReadout) -> str:
    """渲染 case 读出为 JSON 文本。"""
    return json.dumps(readout.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
