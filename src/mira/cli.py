"""``mira`` 命令行入口：init / validate / refresh / report。

用法::

    mira init <dir>                 # 生成最小 case 骨架（默认全绿）
    mira validate [路径...] --all   # 契约校验（文件/目录/整个仓库）
    mira refresh <case> [--write]   # 刷新报告（fresh/due_soon/expired）
    mira report  <case>             # 研究包读出（Markdown/JSON）

退出码：0 全部通过；1 存在校验错误；2 用法/输入错误。
零第三方依赖即可运行 JSON 校验；YAML 产物需要 PyYAML。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from . import evidence as ev
from . import refresh as rf
from . import report as rp
from .config import Config, load_config, take_warnings
from .contracts import (
    ArtifactCheck,
    check_document,
    check_evidence_csv,
    check_package_dir,
    load_document,
    scan_targets,
    take_load_errors,
    validate_schemas_selfcheck,
)
from .scaffold import init_workspace


def _force_utf8() -> None:
    """Windows 控制台默认 cp936，统一为 UTF-8 输出避免乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


# ---------------------------------------------------------------- validate

def _collect_targets(args_paths: List[str], config: Config, all_mode: bool) -> List[Any]:
    """把命令行路径 / --all 展开为待校验目标列表。

    返回元素为 Path（文件或目录）；evidence-log.csv 由 :func:`cmd_validate` 特判。
    """
    targets: List[Path] = []
    for raw in args_paths:
        targets.append(Path(raw))
    if all_mode:
        examples = config.path("examples")
        if examples.exists():
            targets.extend(sorted(p for p in examples.rglob("*") if p.is_file()))
    return targets


def _check_any(path: Path, schemas_dir: Path, force_schema: Optional[str]) -> List[ArtifactCheck]:
    if path.is_dir():
        return scan_targets(path, schemas_dir)
    if path.name == "evidence-log.csv":
        return [check_evidence_csv(path, schemas_dir)]
    if path.suffix.lower() in (".json", ".yaml", ".yml"):
        return [check_document(path, schemas_dir, force_kind=force_schema)]
    return []


def cmd_validate(args: argparse.Namespace, config: Config) -> int:
    """执行 mira validate。"""
    schemas_dir = config.schemas_path
    targets = _collect_targets(args.paths, config, args.all)
    if not targets and not args.all:
        print("用法: mira validate <路径...> [--all]（或 mira validate --all 校验整个仓库）", file=sys.stderr)
        return 2

    checks: List[ArtifactCheck] = []
    for target in targets:
        if not target.exists():
            from .jsonschema_lite import ValidationError

            checks.append(
                ArtifactCheck(str(target), None, [ValidationError("$", "exists", "路径不存在")])
            )
            continue
        checks.extend(_check_any(target, schemas_dir, args.schema))

    schema_problems: List[str] = []
    if args.all:
        schema_problems = validate_schemas_selfcheck(schemas_dir)

    ok_count = sum(1 for check in checks if check.ok)
    failed = [check for check in checks if not check.ok]

    if args.json:
        payload: Dict[str, Any] = {
            "targets": [
                {
                    "path": check.path,
                    "kind": check.kind,
                    "ok": check.ok,
                    "errors": [e.render() for e in check.errors],
                    "notes": check.notes,
                }
                for check in checks
            ],
            "schemas_selfcheck": schema_problems,
            "summary": {"total": len(checks), "passed": ok_count, "failed": len(failed)},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            kind = check.kind or "未识别"
            if check.ok:
                flag = "通过"
            else:
                flag = "失败"
            print(f"[{flag}] {check.path}（{kind}）")
            for note in check.notes:
                print(f"    · {note}")
            for error in check.errors:
                print(f"    ✗ {error.render()}")
        for problem in schema_problems:
            print(f"[失败] schemas 自检: {problem}")
        for warning in take_warnings() + take_load_errors():
            print(f"[提示] {warning}")
        print(f"\n共 {len(checks)} 项：通过 {ok_count}，失败 {len(failed)}；schema 自检问题 {len(schema_problems)}")

    return 1 if (failed or schema_problems) else 0


# ---------------------------------------------------------------- init

def cmd_init(args: argparse.Namespace, config: Config) -> int:
    """执行 mira init。"""
    dest = Path(args.directory)
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else config.as_of_date()
    stale_after = dt.date.fromisoformat(args.stale_after) if args.stale_after else None
    try:
        created = init_workspace(
            dest,
            thesis_id=args.thesis_id or dest.name,
            title=args.title,
            research_object=args.object or "待填写研究对象",
            market_scope=args.market or "A股/美股（待确认）",
            horizon=args.horizon,
            as_of=as_of,
            stale_after=stale_after,
            due_soon_days=args.due_soon_days or config.due_soon_days,
            fmt="json" if args.json else "yaml",
            force=args.force,
        )
    except FileExistsError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    for path in created:
        print(f"已生成 {path}")
    print(f"\n下一步: mira validate {dest.as_posix()}")
    return 0


# ---------------------------------------------------------------- refresh

def _resolve_case(path: Path) -> Dict[str, Optional[Path]]:
    if path.is_dir():
        return rf.find_case_files(path)
    return rf.find_case_files(path.parent)


def cmd_refresh(args: argparse.Namespace, config: Config) -> int:
    """执行 mira refresh。"""
    case_path = Path(args.case)
    if not case_path.exists():
        print(f"错误: 路径不存在: {case_path}", file=sys.stderr)
        return 2
    files = _resolve_case(case_path)
    card_path = files["card"]
    if card_path is None and case_path.is_file() and case_path.suffix.lower() in (".yaml", ".yml", ".json"):
        card_path = case_path
    if card_path is None:
        print(f"错误: 未找到论点卡（thesis-card.yaml/json）: {case_path}", file=sys.stderr)
        return 2

    try:
        card = load_document(card_path)
    except Exception as exc:
        print(f"错误: 论点卡无法解析: {exc}", file=sys.stderr)
        return 2

    plan = rf.load_plan(files["plan"])
    log: Optional[ev.EvidenceLog] = None
    if files["evidence"] is not None:
        try:
            log = ev.read_log(files["evidence"])
        except ValueError as exc:
            print(f"提示: 证据日志跳过（{exc}）")

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else config.as_of_date()
    due_soon_days = args.due_soon_days if args.due_soon_days is not None else config.due_soon_days
    report = rf.build_refresh_report(card, plan, log, as_of=as_of, due_soon_days=due_soon_days)

    rendered = rf.render_json(report) if args.format == "json" else rf.render_markdown(report)
    if args.write and case_path.is_dir():
        md_path = case_path / "refresh-report.md"
        json_path = case_path / "refresh-report.json"
        md_path.write_text(rf.render_markdown(report), encoding="utf-8")
        json_path.write_text(rf.render_json(report), encoding="utf-8")
        print(f"已写入 {md_path}")
        print(f"已写入 {json_path}")
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"已写入 {args.output}")
    if not args.write and not args.output:
        sys.stdout.write(rendered)
    return 0


# ---------------------------------------------------------------- report

def cmd_report(args: argparse.Namespace, config: Config) -> int:
    """执行 mira report。"""
    case_dir = Path(args.case)
    if not case_dir.exists() or not case_dir.is_dir():
        print(f"错误: 需要一个 case 目录: {case_dir}", file=sys.stderr)
        return 2
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else config.as_of_date()
    due_soon_days = args.due_soon_days if args.due_soon_days is not None else config.due_soon_days
    readout = rp.build_readout(case_dir, as_of=as_of, due_soon_days=due_soon_days)
    rendered = rp.render_json(readout) if args.format == "json" else rp.render_markdown(readout)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"已写入 {args.output}")
    else:
        sys.stdout.write(rendered)
    return 0


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    """构造 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        prog="mira",
        description="Mira —— 证据追踪型投研工作区：契约校验 / 刷新报告 / 研究包读出",
    )
    parser.add_argument("--version", action="version", version=f"mira {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="生成最小 case 骨架")
    p_init.add_argument("directory", help="目标目录（同时作为 case_id，除非显式指定 --thesis-id）")
    p_init.add_argument("--thesis-id", default=None)
    p_init.add_argument("--title", default=None)
    p_init.add_argument("--object", default=None, help="研究对象")
    p_init.add_argument("--market", default=None, help="市场范围")
    p_init.add_argument("--horizon", default="fundamental", choices=["trading", "fundamental", "industrial_trend"])
    p_init.add_argument("--as-of", default=None, help="YYYY-MM-DD（默认今天）")
    p_init.add_argument("--stale-after", default=None, help="YYYY-MM-DD（默认 as-of + 90 天）")
    p_init.add_argument("--due-soon-days", type=int, default=None)
    p_init.add_argument("--json", action="store_true", help="生成 .json 而非 .yaml 的论点卡/刷新计划")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在文件")
    p_init.set_defaults(func=cmd_init)

    p_validate = sub.add_parser("validate", help="契约校验")
    p_validate.add_argument("paths", nargs="*", default=[], help="文件或目录（目录递归）")
    p_validate.add_argument("--all", action="store_true", help="校验 examples/ 全部内容 + schemas 自检")
    p_validate.add_argument("--schema", default=None, help="强制按指定契约校验（thesis-card/evidence/refresh/monitoring/routing/research-package）")
    p_validate.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    p_validate.set_defaults(func=cmd_validate)

    p_refresh = sub.add_parser("refresh", help="生成刷新报告")
    p_refresh.add_argument("case", help="case 目录或论点卡文件")
    p_refresh.add_argument("--as-of", default=None, help="YYYY-MM-DD（默认配置/今天）")
    p_refresh.add_argument("--due-soon-days", type=int, default=None)
    p_refresh.add_argument("--format", choices=["md", "json"], default="md")
    p_refresh.add_argument("-o", "--output", default=None, help="输出文件路径")
    p_refresh.add_argument("--write", action="store_true", help="写入 case 目录的 refresh-report.md/json")
    p_refresh.set_defaults(func=cmd_refresh)

    p_report = sub.add_parser("report", help="研究包读出")
    p_report.add_argument("case", help="case 目录")
    p_report.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    p_report.add_argument("--due-soon-days", type=int, default=None)
    p_report.add_argument("--format", choices=["md", "json"], default="md")
    p_report.add_argument("-o", "--output", default=None, help="输出文件路径")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主入口，返回退出码。"""
    _force_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    return int(args.func(args, config))


def entry() -> None:
    """console_scripts 入口。"""
    raise SystemExit(main())
