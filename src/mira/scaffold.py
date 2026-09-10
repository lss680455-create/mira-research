"""``mira init`` 的脚手架：生成一套通过契约校验的最小 case 骨架。

生成物（默认 YAML 形态，``--json`` 可切换为纯 JSON）：

* ``research-package.json`` —— 包清单（入口）
* ``thesis-card.yaml`` —— 论点卡（draft 态，字段带 TODO 占位）
* ``refresh.yaml`` —— 刷新计划（含一条 time 触发条件示例）
* ``monitoring.json`` —— 监控队列（一条 open 项）
* ``routing.json`` —— 路由卡（standard 深度模板）
* ``evidence-log.csv`` —— canonical v1.2 空表（仅表头）
* ``README.md`` —— case 使用说明

骨架初始即为「校验全绿」，用户按 TODO 逐步替换占位内容即可。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

from .evidence import CANONICAL_COLUMNS_V12
from .refresh import time_status


def _dump(path: Path, data: object, fmt: str) -> None:
    if fmt == "json" or path.suffix == ".json":
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    import yaml  # type: ignore

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _yaml_or_json(base: Path, name: str, fmt: str) -> Path:
    if fmt == "json":
        return base / f"{name}.json"
    return base / f"{name}.yaml"


def init_workspace(
    dest: Path,
    *,
    thesis_id: Optional[str] = None,
    title: Optional[str] = None,
    research_object: str = "待填写研究对象",
    market_scope: str = "A股/美股（待确认）",
    horizon: str = "fundamental",
    as_of: Optional[dt.date] = None,
    stale_after: Optional[dt.date] = None,
    due_soon_days: int = 30,
    fmt: str = "yaml",
    force: bool = False,
) -> List[Path]:
    """在 ``dest`` 生成最小 case 骨架，返回写出的文件路径列表。"""
    as_of = as_of or dt.date.today()
    stale_after = stale_after or (as_of + dt.timedelta(days=90))
    case_id = thesis_id or dest.name
    title = title or f"{case_id} 论点卡（草稿）"

    dest.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []

    def write(path: Path, data: object) -> None:
        if path.exists() and not force:
            raise FileExistsError(f"文件已存在（--force 可覆盖）: {path}")
        _dump(path, data, fmt)
        created.append(path)

    status = time_status(as_of, stale_after, due_soon_days)

    # 1) 包清单
    write(
        dest / "research-package.json",
        {
            "manifest_version": "mira_research_package_v1",
            "case_id": case_id,
            "research_object": research_object,
            "market_scope": market_scope,
            "research_cutoff_date": as_of.isoformat(),
            "package_type": "research_package",
            "readiness_level": "draft",
            "readiness_basis": "init 模板：尚未填充证据",
            "research_action": "add_to_research_queue",
            "action_boundary": "research_action_only_not_trade_instruction",
            "blocking_gaps": ["论点卡与证据日志待填充（search TODO）"],
            "primary_workflow": "workflows/research-loop.md",
            "thesis_card": _yaml_or_json(dest, "thesis-card", fmt).name,
            "hero_artifacts": [_yaml_or_json(dest, "thesis-card", fmt).name],
            "support_artifacts": [
                "evidence-log.csv",
                "routing.json",
                "monitoring.json",
                _yaml_or_json(dest, "refresh", fmt).name,
            ],
            "source_scope": "待填写：来源范围与语言",
            "evidence_log_status": "canonical_v1_2",
            "stale_after": stale_after.isoformat(),
            "must_refresh_if": [
                f"超过时间边界（{stale_after.isoformat()}）仍未复核",
                "关键变量的反证信号出现但未回写证据日志",
            ],
        },
    )

    # 2) 论点卡（保持可校验的 draft）
    write(
        _yaml_or_json(dest, "thesis-card", fmt),
        {
            "schema_version": "1.0",
            "thesis_id": case_id,
            "title": title,
            "research_object": research_object,
            "market_scope": market_scope,
            "horizon": horizon if horizon in ("trading", "fundamental", "industrial_trend") else "fundamental",
            "state": "draft",
            "confidence": "low",
            "core_claim": "TODO：一句话写出本论点（可被证伪的陈述句）",
            "variant_view": "TODO：与共识的差异在哪里",
            "key_variables": [
                {
                    "variable": "TODO：关键变量",
                    "consensus_proxy": "TODO：共识用什么数字/口径表达",
                    "mira_view": "TODO：Mira 认为会怎么走",
                    "price_in_status": "unknown",
                }
            ],
            "key_assumptions": ["TODO：写下成立所依赖的关键假设"],
            "evidence_ids": ["TODO-0001"],
            "disconfirming_evidence": ["TODO：写出一个可观测的证伪信号"],
            "refresh": {
                "stale_after": stale_after.isoformat(),
                "must_refresh_if": [
                    f"超过 {stale_after.isoformat()} 未复核",
                    "出现直接反驳 core_claim 的一手证据",
                ],
            },
            "notes": "init 模板生成；完成填充后删除本行。",
        },
    )

    # 3) 刷新计划
    write(
        _yaml_or_json(dest, "refresh", fmt),
        {
            "schema_version": "1.0",
            "thesis_id": case_id,
            "as_of": as_of.isoformat(),
            "stale_after": stale_after.isoformat(),
            "refresh_status": status,
            "triggers": [
                {
                    "trigger_id": "T-time",
                    "kind": "time",
                    "condition": f"到达时间边界 {stale_after.isoformat()} 前需用新数据复核",
                    "status": "pending",
                    "last_checked": as_of.isoformat(),
                    "next_check": (as_of + dt.timedelta(days=30)).isoformat(),
                    "action_if_fired": "重跑研究循环并更新论点卡与证据日志",
                }
            ],
            "must_refresh_if": [
                f"超过 {stale_after.isoformat()} 未复核",
                "关键变量出现反向证据",
            ],
            "notes": "init 模板生成；建议随研究推进补充事件类触发条件。",
        },
    )

    # 4) 监控队列
    write(
        dest / "monitoring.json",
        {
            "schema_version": "1.0",
            "queue_id": f"q-{case_id}",
            "created_at": as_of.isoformat(),
            "items": [
                {
                    "thesis_id": case_id,
                    "variable": "TODO：待监控变量",
                    "watch_source": "TODO：来源（公告/财报/行业数据）",
                    "cadence": "weekly",
                    "escalation_condition": "TODO：出现什么信号退回研究循环",
                    "status": "open",
                    "last_checked": as_of.isoformat(),
                    "next_check": (as_of + dt.timedelta(days=7)).isoformat(),
                }
            ],
        },
    )

    # 5) 路由卡
    write(
        dest / "routing.json",
        {
            "schema_version": "1.0",
            "interaction_mode": "routed_research",
            "primary_intent": "首轮研究：建立论点卡与证据基线",
            "task_mode": "first_pass_research",
            "research_object": research_object,
            "market_scope": market_scope,
            "time_boundary": f"{as_of.isoformat()} 截止",
            "depth_mode": "standard",
            "decision_pressure": "none",
            "framing_risk": "none",
            "disconfirmation_required": "yes",
            "quant_dependency": "low",
            "calculation_gate": "not_required",
            "primary_workflow": "workflows/research-loop.md",
            "expected_output_package": f"research_package（{case_id}）",
            "readiness_level": "draft",
            "routing_basis": "init 模板：按 standard 深度首轮研究路由",
            "followup_prompt_mode": "standard",
            "followup_questions": [
                "验证论点所需的最小证据集是什么？",
                "什么信号出现时应放弃该论点？",
            ],
        },
    )

    # 6) 证据日志（只看表头）
    header_path = dest / "evidence-log.csv"
    if header_path.exists() and not force:
        raise FileExistsError(f"文件已存在（--force 可覆盖）: {header_path}")
    header_path.write_text(",".join(CANONICAL_COLUMNS_V12) + "\n", encoding="utf-8")
    created.append(header_path)

    # 7) case 说明
    readme_path = dest / "README.md"
    if readme_path.exists() and not force:
        raise FileExistsError(f"文件已存在（--force 可覆盖）: {readme_path}")
    readme_path.write_text(
        f"""# {case_id} · 研究包

本目录由 `mira init` 生成，是一套通过契约校验的最小研究包骨架。

- 论点卡：`{_yaml_or_json(dest, 'thesis-card', fmt).name}`
- 刷新计划：`{_yaml_or_json(dest, 'refresh', fmt).name}`
- 证据日志：`evidence-log.csv`（canonical v1.2 表头）
- 包清单：`research-package.json`

## 使用

```bash
mira validate {dest.as_posix()}          # 契约校验
mira refresh {dest.as_posix()} --as-of {as_of.isoformat()}   # 刷新报告
mira report {dest.as_posix()} --as-of {as_of.isoformat()}    # 研究包读出
```

把 thesis-card 里的 TODO 替换为真实内容；每新增一条证据，向 `evidence-log.csv`
追加一行（列序不变），并在论点卡 `evidence_ids` 中引用其 source_id。
""",
        encoding="utf-8",
    )
    created.append(readme_path)

    return created
