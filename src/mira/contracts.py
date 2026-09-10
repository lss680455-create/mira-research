"""契约层：schema 装载、artifact 类型识别、统一校验入口。

契约文件位于 ``schemas/``：

* ``vocab.json`` —— 受控词表（唯一来源，schema 通过 $ref 引用）；
* ``thesis-card.schema.json`` / ``evidence.schema.json`` /
  ``refresh.schema.json`` / ``monitoring.schema.json`` /
  ``routing.schema.json`` / ``research-package.schema.json`` —— 六类 artifact 契约。

本模块同时提供 artifact 的自动识别（按文件名 + 顶层字段特征），供
``mira validate`` 对任意 JSON/YAML 文件做归类校验。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .jsonschema_lite import SchemaError, ValidationError, make_file_resolver, validate

#: 六类 artifact 契约（key = 契约名，value = schema 文件名）。
SCHEMAS: Dict[str, str] = {
    "thesis-card": "thesis-card.schema.json",
    "evidence": "evidence.schema.json",
    "refresh": "refresh.schema.json",
    "monitoring": "monitoring.schema.json",
    "routing": "routing.schema.json",
    "research-package": "research-package.schema.json",
}

#: 契约名 → YAML/JSON 里应出现的 flag 字段（用于自动识别）。
_SIGNATURE_FIELDS: Dict[str, Tuple[str, ...]] = {
    "thesis-card": ("core_claim", "key_variables", "disconfirming_evidence"),
    "evidence": ("claim_type", "evidence_category", "readiness_impact"),
    "refresh": ("refresh_status", "triggers", "must_refresh_if"),
    "monitoring": ("queue_id", "items"),
    "routing": ("routing_basis", "depth_mode", "followup_prompt_mode"),
    "research-package": ("manifest_version", "hero_artifacts"),
}

#: 文件名（不含扩展名）→ 契约名。
_FILENAME_HINTS: Dict[str, str] = {
    "thesis-card": "thesis-card",
    "thesis": "thesis-card",
    "refresh": "refresh",
    "refresh-plan": "refresh",
    "monitoring": "monitoring",
    "routing": "routing",
    "research-package": "research-package",
    "research-package-manifest": "research-package",
}

_LOAD_ERRORS: List[str] = []


def take_load_errors() -> List[str]:
    """取出（并清空）schema 装载过程中的错误信息。"""
    out = list(_LOAD_ERRORS)
    _LOAD_ERRORS.clear()
    return out


@dataclass
class ArtifactCheck:
    """单个文件的校验结果。"""

    path: str
    kind: Optional[str]
    errors: List[ValidationError] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_document(path: Path) -> Any:
    """读取 JSON 或 YAML 文档（按扩展名分派）。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore

        return yaml.safe_load(text)
    return json.loads(text)


def load_schema(schemas_dir: Path, kind: str) -> Dict[str, Any]:
    """按契约名装载 schema；未知契约名抛 ``KeyError``。"""
    filename = SCHEMAS[kind]
    with (schemas_dir / filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def detect_kind(path: Path, data: Any) -> Optional[str]:
    """识别 artifact 类型：先看文件名，再看顶层字段特征。"""
    stem = path.stem.lower()
    if stem in _FILENAME_HINTS:
        hint = _FILENAME_HINTS[stem]
        if hint == "thesis-card" and not _looks_like(data, hint):
            return None
        return hint
    if isinstance(data, dict):
        for kind, fields in _SIGNATURE_FIELDS.items():
            if all(field in data for field in fields):
                return kind
    return None


def _looks_like(data: Any, kind: str) -> bool:
    if not isinstance(data, dict):
        return False
    fields = _SIGNATURE_FIELDS[kind]
    hit = sum(1 for field in fields if field in data)
    return hit >= max(1, len(fields) - 1)


def validate_artifact(schemas_dir: Path, kind: str, data: Any) -> List[ValidationError]:
    """用 ``kind`` 对应契约校验 ``data``，返回错误列表。"""
    schema = load_schema(schemas_dir, kind)
    resolver = make_file_resolver(schemas_dir)
    return validate(data, schema, resolver=resolver)


def check_document(path: Path, schemas_dir: Path, force_kind: Optional[str] = None) -> ArtifactCheck:
    """校验单个文档文件；无法识别类型时给出 note 而不是报错。"""
    try:
        data = load_document(path)
    except Exception as exc:
        return ArtifactCheck(str(path), force_kind, [], [f"无法解析文件: {exc}"])

    kind = force_kind or detect_kind(path, data)
    if kind is None:
        return ArtifactCheck(str(path), None, [], ["未识别的 artifact 类型，已跳过"])
    if kind not in SCHEMAS:
        return ArtifactCheck(str(path), kind, [], [f"未知契约 {kind!r}，已跳过"])
    try:
        errors = validate_artifact(schemas_dir, kind, data)
    except SchemaError as exc:
        return ArtifactCheck(str(path), kind, [], [f"schema 装载失败: {exc}"])
    return ArtifactCheck(str(path), kind, errors)


def check_evidence_csv(path: Path, schemas_dir: Path) -> ArtifactCheck:
    """校验 evidence-log.csv：结构层 + 业务层 + 逐行契约（v1.2/v1.1）。"""
    from . import evidence as ev

    try:
        log = ev.read_log(path)
    except Exception as exc:
        return ArtifactCheck(str(path), "evidence-log", [ValidationError("$", "read", str(exc))])

    errors: List[ValidationError] = []
    notes: List[str] = [f"表头 {log.version} · {len(log.rows)} 行"]
    for issue in ev.validate_log(log, schemas_dir):
        if issue.level == "error":
            errors.append(ValidationError(f"$.rows[{issue.row}]", f"evidence:{issue.field}", issue.message))
        else:
            notes.append(issue.render())

    if log.version in ("v1.2", "v1.1"):
        for row_index, record in ev.rows_as_records(log):
            try:
                row_errors = validate_artifact(schemas_dir, "evidence", record)
            except SchemaError as exc:  # pragma: no cover - schema 装载失败
                notes.append(f"逐行契约校验跳过（{exc}）")
                break
            for err in row_errors:
                errors.append(
                    ValidationError(f"$.rows[{row_index}]{err.path[1:]}", f"contract:{err.keyword}", err.message)
                )
    else:
        notes.append("legacy v1 表头：跳过逐行契约校验，建议迁移 v1.2")

    return ArtifactCheck(str(path), "evidence-log", errors, notes)


def check_package_dir(package_dir: Path, schemas_dir: Path) -> List[ArtifactCheck]:
    """校验一个 case 目录：manifest 的产物清单必须与实际文件对得上。

    校验范围：
      * ``research-package.json``（或 legacy 名 ``research-package-manifest.json``）；
      * manifest 里声明的 hero/support 产物逐个校验（存在性 + 契约）；
      * 目录内其余可识别的 json/yaml（thesis-card / routing / refresh / monitoring）。
    """
    results: List[ArtifactCheck] = []
    manifest_path = None
    for candidate in ("research-package.json", "research-package-manifest.json"):
        if (package_dir / candidate).exists():
            manifest_path = package_dir / candidate
            break

    manifest_data: Optional[dict] = None
    if manifest_path is not None:
        manifest_check = check_document(manifest_path, schemas_dir, force_kind="research-package")
        results.append(manifest_check)
        try:
            manifest_data = load_document(manifest_path)
        except Exception:
            manifest_data = None
    else:
        results.append(
            ArtifactCheck(str(package_dir), "research-package", [ ValidationError("$", "required", "case 目录缺少 research-package.json") ])
        )

    if isinstance(manifest_data, dict):
        declared: List[str] = list(manifest_data.get("hero_artifacts", []) or []) + list(
            manifest_data.get("support_artifacts", []) or []
        )
        for rel in declared:
            target = package_dir / rel
            if not target.exists():
                results.append(
                    ArtifactCheck(
                        str(target),
                        None,
                        [ValidationError("$", "required", "manifest 声明的产物不存在")],
                    )
                )

    known_names = {
        "thesis-card.yaml", "thesis-card.yml", "thesis-card.json",
        "routing.json", "refresh.yaml", "refresh.yml", "refresh.json",
        "monitoring.json",
    }
    for child in sorted(package_dir.iterdir()):
        if not child.is_file():
            continue
        if child.name in known_names:
            results.append(check_document(child, schemas_dir))
        elif child.name == "evidence-log.csv":
            results.append(check_evidence_csv(child, schemas_dir))
    return results


def scan_targets(target: Path, schemas_dir: Path) -> List[ArtifactCheck]:
    """对 ``mira validate`` 的路径参数做分派：目录走包校验，文件走单件校验。"""
    if target.is_dir():
        if (target / "research-package.json").exists() or (target / "research-package-manifest.json").exists():
            return check_package_dir(target, schemas_dir)
        results: List[ArtifactCheck] = []
        for child in sorted(target.rglob("*")):
            if child.is_dir():
                continue
            if child.name == "evidence-log.csv":
                results.append(check_evidence_csv(child, schemas_dir))
                continue
            if child.suffix.lower() not in (".json", ".yaml", ".yml"):
                continue
            check = check_document(child, schemas_dir)
            if check.kind is not None:
                results.append(check)
        return results
    if target.name == "evidence-log.csv":
        return [check_evidence_csv(target, schemas_dir)]
    return [check_document(target, schemas_dir)]


def validate_schemas_selfcheck(schemas_dir: Path) -> List[str]:
    """自检：schemas 目录里每个 schema 都可以被解析、且 $ref 可解析。"""
    problems: List[str] = []
    resolver = make_file_resolver(schemas_dir)
    for filename in sorted(schemas_dir.glob("*.schema.json")):
        try:
            schema = json.loads(filename.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"{filename.name}: 无法解析 ({exc})")
            continue
        refs = _collect_refs(schema)
        for ref in sorted(refs):
            try:
                resolver(ref)
            except SchemaError as exc:
                problems.append(f"{filename.name}: {exc}")
    try:
        vocab = json.loads((schemas_dir / "vocab.json").read_text(encoding="utf-8"))
        for key, value in vocab.items():
            if key.startswith("$"):
                continue
            if not (isinstance(value, dict) and isinstance(value.get("enum"), list) and value["enum"]):
                problems.append(f"vocab.json: {key} 不是非空 enum 定义")
    except Exception as exc:
        problems.append(f"vocab.json: 无法解析 ({exc})")
    return problems


def _collect_refs(node: Any, acc: Optional[set] = None) -> set:
    if acc is None:
        acc = set()
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str):
            acc.add(node["$ref"])
        for value in node.values():
            _collect_refs(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, acc)
    return acc
