"""证据面：evidence-log.csv 的读取、列契约与业务规则校验。

canonical 载体是 case 级 ``evidence-log.csv``（v1.2，22 列，列序固定）；
v1 / v1.1 表头作为 legacy 兼容读取但会在校验结果里提示。校验分两层：

1. 结构层 —— 表头与列序、必填、枚举、日期格式；
2. 业务层 —— 派生计算必须有上游来源、弱信号不得高置信、姿态一致性等；
3. 语义层 —— 每行可转换为 evidence.schema.json 的 JSON 记录做契约校验
   （见 :func:`rows_as_records`，由 ``mira validate`` 串联）。
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

#: v1.2 表头（canonical，22 列，顺序即契约）。
CANONICAL_COLUMNS_V12: Tuple[str, ...] = (
    "source_id",
    "claim_area",
    "claim_type",
    "claim_text",
    "source_speaker",
    "verification_status",
    "authority_level",
    "source_date",
    "as_of_date",
    "url_or_path",
    "used_by_agent",
    "used_by_skill",
    "confidence",
    "upstream_sources",
    "notes",
    "evidence_category",
    "freshness_status",
    "conflict_status",
    "treatment",
    "readiness_impact",
    "source_language",
    "translation_basis",
)

#: 历史版本表头（纯追加迁移：v1 → v1.1 → v1.2 不改变既有列序）。
LEGACY_V11_COLUMNS: Tuple[str, ...] = CANONICAL_COLUMNS_V12[:20]
LEGACY_V1_COLUMNS: Tuple[str, ...] = CANONICAL_COLUMNS_V12[:15]

VERSIONS: Dict[str, Tuple[str, ...]] = {
    "v1.2": CANONICAL_COLUMNS_V12,
    "v1.1": LEGACY_V11_COLUMNS,
    "v1": LEGACY_V1_COLUMNS,
}

#: 判断性 claim（翻译纪律要求保留原文片段）。
JUDGMENT_CLAIM_TYPES = {"guidance", "company_claim", "commitment", "target"}

REQUIRED_FIELDS: Tuple[str, ...] = CANONICAL_COLUMNS_V12


@dataclass
class EvidenceIssue:
    """单条校验问题（row 为 None 表示表头/文件级问题）。"""

    level: str  # "error" | "warn"
    row: Optional[int]
    field: str
    message: str

    def render(self) -> str:
        where = "表头" if self.row is None else f"第 {self.row} 行"
        return f"[{self.level}] {where} · {self.field}: {self.message}"


@dataclass
class EvidenceLog:
    """一条 evidence-log.csv 的全部内容 + 版本信息。"""

    path: Path
    version: str
    columns: Tuple[str, ...]
    rows: List[Dict[str, str]] = field(default_factory=list)

    @property
    def is_canonical(self) -> bool:
        return self.version == "v1.2"


def detect_version(columns: Tuple[str, ...]) -> Optional[str]:
    """按表头识别版本；无法识别返回 None。"""
    for version, expected in VERSIONS.items():
        if tuple(columns) == expected:
            return version
    return None


def read_log(path: Path) -> EvidenceLog:
    """读取 evidence-log.csv。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 表头无法识别为任何已知版本。
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = tuple(next(reader))
        except StopIteration as exc:  # 空文件
            raise ValueError(f"evidence-log 为空文件: {path}") from exc
        version = detect_version(header)
        if version is None:
            raise ValueError(
                f"表头与 canonical v1.2 / legacy v1.1 / v1 均不一致: {path}\n实际表头: {','.join(header)}"
            )
        rows: List[Dict[str, str]] = []
        for line_no, values in enumerate(reader, start=2):
            if not values or all(not value.strip() for value in values):
                continue
            if len(values) != len(header):
                rows.append({"__malformed__": f"第 {line_no} 行列数 {len(values)} != 表头列数 {len(header)}"})
                continue
            rows.append({key: value.strip() for key, value in zip(header, values)})
        return EvidenceLog(path=path, version=version, columns=header, rows=rows)


def _load_vocab(schemas_dir: Optional[Path]) -> Dict[str, Any]:
    """从 schemas/vocab.json 读取枚举（找不到时返回空表，枚举检查退化为跳过）。"""
    if schemas_dir is None:
        return {}
    vocab_path = Path(schemas_dir) / "vocab.json"
    if not vocab_path.exists():
        return {}
    with vocab_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _enum(vocab: Dict[str, Any], key: str) -> Optional[set]:
    value = vocab.get(key)
    if isinstance(value, dict) and isinstance(value.get("enum"), list):
        return set(value["enum"])
    return None


def _is_date(text: str) -> bool:
    try:
        _dt.date.fromisoformat(text)
        return True
    except ValueError:
        return False


def validate_log(log: EvidenceLog, schemas_dir: Optional[Path] = None) -> List[EvidenceIssue]:
    """按结构层 + 业务层规则校验 evidence log，返回问题列表（不抛异常）。"""
    issues: List[EvidenceIssue] = []
    vocab = _load_vocab(schemas_dir)

    if not log.is_canonical:
        issues.append(
            EvidenceIssue(
                "warn",
                None,
                "version",
                f"legacy 表头（{log.version}）；新 case 应使用 canonical v1.2（22 列）",
            )
        )

    checks: List[Tuple[str, str]] = [
        ("claim_type", "claim_type"),
        ("verification_status", "verification_status"),
        ("authority_level", "authority_level"),
        ("confidence", "confidence"),
        ("evidence_category", "evidence_category"),
        ("freshness_status", "freshness_status"),
        ("conflict_status", "conflict_status"),
        ("treatment", "treatment"),
        ("readiness_impact", "readiness_impact"),
    ]
    if log.is_canonical:
        checks.extend([("source_language", "source_language"), ("translation_basis", "translation_basis")])

    for row_index, row in enumerate(log.rows, start=2):
        if "__malformed__" in row:
            issues.append(EvidenceIssue("error", row_index, "(row)", row["__malformed__"]))
            continue

        for field_name in REQUIRED_FIELDS:
            if field_name not in row:
                continue  # legacy 缺列由版本检查覆盖
            if not row[field_name]:
                issues.append(EvidenceIssue("error", row_index, field_name, "必填字段为空"))

        for field_name, vocab_key in checks:
            if field_name not in row or not row[field_name]:
                continue
            allowed = _enum(vocab, vocab_key)
            if allowed is not None and row[field_name] not in allowed:
                issues.append(
                    EvidenceIssue("error", row_index, field_name, f"取值 {row[field_name]!r} 不在允许枚举 {sorted(allowed)} 中")
                )

        for field_name in ("source_date", "as_of_date"):
            value = row.get(field_name, "")
            if value and not _is_date(value):
                issues.append(EvidenceIssue("error", row_index, field_name, f"日期应为 YYYY-MM-DD: {value!r}"))

        claim_type = row.get("claim_type", "")
        authority = row.get("authority_level", "")
        upstream = row.get("upstream_sources", "")
        confidence = row.get("confidence", "")
        category = row.get("evidence_category", "")
        verification = row.get("verification_status", "")
        readiness = row.get("readiness_impact", "")
        notes = row.get("notes", "")

        if (claim_type == "derived_calculation" or authority == "L6") and (
            not upstream or upstream == "not_applicable"
        ):
            issues.append(
                EvidenceIssue(
                    "error",
                    row_index,
                    "upstream_sources",
                    "derived_calculation / L6 记录必须列出上游来源 id（不能为空或 not_applicable）",
                )
            )
        if claim_type == "rumor_signal" and confidence == "high":
            issues.append(EvidenceIssue("error", row_index, "confidence", "rumor_signal 不得标 high 置信度"))
        if category == "verified_fact" and verification == "unverified":
            issues.append(
                EvidenceIssue(
                    "error",
                    row_index,
                    "evidence_category",
                    "verified_fact 不允许搭配 verification_status=unverified",
                )
            )
        if readiness == "supports_durable_conclusion" and category in {"unknown", "weak_signal", "stale", "contradicted"}:
            if not notes:
                issues.append(
                    EvidenceIssue(
                        "error",
                        row_index,
                        "readiness_impact",
                        f"{category} 姿态不得无说明地声明 supports_durable_conclusion（需在 notes 记录降级控制）",
                    )
                )
            else:
                issues.append(
                    EvidenceIssue(
                        "warn",
                        row_index,
                        "readiness_impact",
                        f"{category} 姿态声明 supports_durable_conclusion，已按 notes 降级处理",
                    )
                )
        if log.is_canonical and claim_type in JUDGMENT_CLAIM_TYPES:
            basis = row.get("translation_basis", "")
            if basis in {"mira_translation", "provider_translation"} and "original_excerpt=" not in notes:
                issues.append(
                    EvidenceIssue(
                        "warn",
                        row_index,
                        "notes",
                        "判断性 claim 的译文行建议保留 original_excerpt=（原文片段），避免丢失措辞信息",
                    )
                )
    return issues


def rows_as_records(log: EvidenceLog) -> Iterator[Tuple[int, Dict[str, Any]]]:
    """把 CSV 行转换为 evidence.schema.json 的 JSON 记录（行号, 记录）。

    legacy v1/v1.1 行缺少的语言列按 ``not_applicable`` 补齐，交由契约层
    继续校验其余字段。
    """
    for row_index, row in enumerate(log.rows, start=2):
        if "__malformed__" in row:
            continue
        upstream_raw = row.get("upstream_sources", "")
        upstream = [part.strip() for part in upstream_raw.split(";") if part.strip()] if upstream_raw else []
        record: Dict[str, Any] = {
            "schema_version": "1.0",
            "evidence_id": row.get("source_id", ""),
            "claim_area": row.get("claim_area", ""),
            "claim_type": row.get("claim_type", ""),
            "claim_text": row.get("claim_text", ""),
            "source": {
                "speaker": row.get("source_speaker", ""),
                "name": row.get("source_id", ""),
                "url_or_path": row.get("url_or_path", ""),
                "source_date": row.get("source_date", ""),
                "as_of_date": row.get("as_of_date", ""),
                "authority_level": row.get("authority_level", ""),
                "verification_status": row.get("verification_status", ""),
                "source_language": row.get("source_language") or "not_applicable",
                "translation_basis": row.get("translation_basis") or "not_applicable",
            },
            "confidence": row.get("confidence", ""),
            "upstream_sources": upstream,
            "evidence_category": row.get("evidence_category", ""),
            "freshness_status": row.get("freshness_status", ""),
            "conflict_status": row.get("conflict_status", ""),
            "treatment": row.get("treatment", ""),
            "readiness_impact": row.get("readiness_impact", ""),
            "used_by_agent": row.get("used_by_agent", ""),
            "used_by_skill": row.get("used_by_skill", ""),
            "notes": row.get("notes", ""),
        }
        yield row_index, record


def stats(log: EvidenceLog) -> Dict[str, Any]:
    """汇总证据面统计（供 report/refresh 使用）。"""
    by_category: Dict[str, int] = {}
    by_treatment: Dict[str, int] = {}
    by_authority: Dict[str, int] = {}
    by_freshness: Dict[str, int] = {}
    stale_rows: List[Dict[str, str]] = []
    blocking_rows: List[Dict[str, str]] = []
    for row in log.rows:
        if "__malformed__" in row:
            continue
        by_category[row.get("evidence_category", "?")] = by_category.get(row.get("evidence_category", "?"), 0) + 1
        by_treatment[row.get("treatment", "?")] = by_treatment.get(row.get("treatment", "?"), 0) + 1
        by_authority[row.get("authority_level", "?")] = by_authority.get(row.get("authority_level", "?"), 0) + 1
        by_freshness[row.get("freshness_status", "?")] = by_freshness.get(row.get("freshness_status", "?"), 0) + 1
        if row.get("freshness_status") == "stale" or row.get("evidence_category") == "stale":
            stale_rows.append(row)
        if row.get("readiness_impact", "").startswith("blocks_"):
            blocking_rows.append(row)
    return {
        "total": sum(1 for row in log.rows if "__malformed__" not in row),
        "by_category": dict(sorted(by_category.items())),
        "by_treatment": dict(sorted(by_treatment.items())),
        "by_authority": dict(sorted(by_authority.items())),
        "by_freshness": dict(sorted(by_freshness.items())),
        "stale_rows": stale_rows,
        "blocking_rows": blocking_rows,
        "version": log.version,
    }
