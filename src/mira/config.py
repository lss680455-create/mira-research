"""集中配置：所有 CLI 默认值来自 ``configs/default.yaml``，可用环境变量覆盖。

约定（与 README/风格规范一致）：

* 仓库内不出现本机绝对路径，全部相对仓库根解析（pathlib）。
* 环境变量覆盖（全部可选项）：``MIRA_CONFIG`` / ``MIRA_AS_OF`` /
  ``MIRA_DUE_SOON_DAYS`` / ``MIRA_EVIDENCE_LOG``。
* 配置缺失或不可解析时回落到内置默认值，并给出一条 warning，而不是崩溃。
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULTS: Dict[str, Any] = {
    "as_of": None,               # None 表示取当天；格式 YYYY-MM-DD
    "due_soon_days": 30,         # stale_after 距今 <= N 天 → due_soon
    "schemas_dir": "schemas",
    "evidence_log": "examples/aapl-2026-04/evidence-log.csv",
    "config_file": "configs/default.yaml",
    "timezone": "Asia/Shanghai",
}

_WARNINGS: List[str] = []


def take_warnings() -> List[str]:
    """取出（并清空）配置加载过程中产生的告警。"""
    out = list(_WARNINGS)
    _WARNINGS.clear()
    return out


def find_repo_root(start: Optional[Path] = None) -> Path:
    """自 ``start`` 向上寻找仓库根（以 ``schemas/vocab.json`` 为标志）。

    找不到时回落到包的上一级目录（``src/`` 的父目录），保证离线也能工作。
    """
    base = Path(start) if start else Path(__file__).resolve()
    for candidate in [base, *base.parents]:
        if (candidate / "schemas" / "vocab.json").exists():
            return candidate
    return Path(__file__).resolve().parents[2]


def _parse_scalar(text: str) -> Any:
    text = text.strip()
    if text in ("null", "~", ""):
        return None
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text.strip("'\"")


def _load_yaml_like(path: Path) -> Dict[str, Any]:
    """读取 YAML 配置。优先 PyYAML；缺失时退化为简单 ``key: value`` 解析。"""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        _WARNINGS.append("PyYAML 未安装，配置按简单 key: value 解析")
    except Exception as exc:  # pragma: no cover - 异常分支保留告警语义
        _WARNINGS.append(f"配置解析失败（{exc}），使用内置默认值")
        return {}
    out: Dict[str, Any] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = _parse_scalar(value)
    return out


@dataclass
class Config:
    """运行时配置（默认值 ← YAML ← 环境变量，优先级从低到高）。"""

    as_of: Optional[str] = None
    due_soon_days: int = 30
    schemas_dir: str = "schemas"
    evidence_log: str = DEFAULTS["evidence_log"]
    timezone: str = DEFAULTS["timezone"]
    repo_root: Path = field(default_factory=find_repo_root)

    def as_of_date(self) -> dt.date:
        """返回本次运行的 as-of 日期（显式配置优先，否则取今天）。"""
        if self.as_of:
            return dt.date.fromisoformat(self.as_of)
        return dt.date.today()

    def path(self, rel: str) -> Path:
        """把仓库内相对路径解析为绝对路径。"""
        return (self.repo_root / rel).resolve()

    @property
    def schemas_path(self) -> Path:
        return self.path(self.schemas_dir)


def load_config(repo_root: Optional[Path] = None) -> Config:
    """加载配置：内置默认值 → configs/default.yaml → 环境变量。"""
    root = find_repo_root(repo_root)
    merged: Dict[str, Any] = dict(DEFAULTS)
    config_path = Path(os.environ.get("MIRA_CONFIG", root / DEFAULTS["config_file"]))
    if config_path.exists():
        merged.update(_load_yaml_like(config_path))
    else:
        _WARNINGS.append(f"未找到配置文件 {config_path}，使用内置默认值")

    if os.environ.get("MIRA_AS_OF"):
        merged["as_of"] = os.environ["MIRA_AS_OF"]
    if os.environ.get("MIRA_DUE_SOON_DAYS"):
        try:
            merged["due_soon_days"] = int(os.environ["MIRA_DUE_SOON_DAYS"])
        except ValueError:
            _WARNINGS.append("MIRA_DUE_SOON_DAYS 不是整数，已忽略")
    if os.environ.get("MIRA_EVIDENCE_LOG"):
        merged["evidence_log"] = os.environ["MIRA_EVIDENCE_LOG"]

    return Config(
        as_of=merged.get("as_of"),
        due_soon_days=int(merged.get("due_soon_days", 30)),
        schemas_dir=str(merged.get("schemas_dir", "schemas")),
        evidence_log=str(merged.get("evidence_log", DEFAULTS["evidence_log"])),
        timezone=str(merged.get("timezone", DEFAULTS["timezone"])),
        repo_root=root,
    )
