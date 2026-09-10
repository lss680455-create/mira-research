"""draft-07 JSON Schema 子集校验器（零第三方依赖）。

为什么自己实现：本项目的契约文件（schemas/*.schema.json）需要在一个
完全离线的环境里被校验，且校核语义要可读、可测、可解释。支持的关
键字范围固定如下，遇到范围外的关键字静默忽略（与 JSON Schema 规范
对未知关键字的要求一致）：

  type / enum / const / required / properties / patternProperties /
  additionalProperties / items（schema 或 tuple 形态）/ minItems /
  maxItems / uniqueItems / minLength / maxLength / pattern /
  minimum / maximum / exclusiveMinimum / exclusiveMaximum / multipleOf /
  allOf / anyOf / oneOf / not / if / then / else / $ref / format

$ref 通过外部 resolver 解析（形如 "vocab.json#/thesis_state"），指
向同一 schema 内部的引用（"#/$defs/x"）也支持。

用法::

    from mira.jsonschema_lite import validate
    errors = validate(instance, schema, resolver=my_resolver)
    if errors:
        print(errors[0].render())
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional

__all__ = ["SchemaError", "ValidationError", "validate", "make_file_resolver"]

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([Zz]|[+-]\d{2}:?\d{2})?$")
_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class SchemaError(ValueError):
    """schema 本身不合法（例如 $ref 无法解析）时抛出。"""


@dataclass(frozen=True)
class ValidationError:
    """单条校验失败的记录。

    Attributes:
        path: 实例内的 JSON 路径（如 ``$.refresh.stale_after``）。
        keyword: 触发失败的关键字（如 ``format``）。
        message: 人类可读的原因。
    """

    path: str
    keyword: str
    message: str

    def render(self) -> str:
        """渲染为一行诊断文本。"""
        return f"{self.path}: [{self.keyword}] {self.message}"


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _json_equal(a: Any, b: Any) -> bool:
    """JSON 语义的相等：布尔与数字不互相等同（True != 1）。"""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _matches_type(value: Any, type_name: str) -> bool:
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    expected = _JSON_TYPES.get(type_name)
    if expected is None:
        return True  # 未知类型名按规范忽略
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    if type_name == "string":
        return isinstance(value, str)
    return isinstance(value, expected)


def _check_format(value: str, fmt: str) -> bool:
    if fmt == "date":
        if not _DATE_RE.match(value):
            return False
        try:
            _dt.date.fromisoformat(value)
            return True
        except ValueError:
            return False
    if fmt == "date-time":
        return bool(_DATETIME_RE.match(value))
    if fmt == "uri":
        return bool(_URI_RE.match(value))
    return True  # 未知 format 不做断言


def _join(path: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}"


class _Validator:
    """一次校验过程的状态容器（含 $ref 环检测）。"""

    def __init__(self, resolver: Optional[Callable[[str], Any]] = None, max_depth: int = 64) -> None:
        self.resolver = resolver
        self.max_depth = max_depth
        self._root_schema: Optional[Any] = None

    # ---- 公共入口 ----
    def validate(self, instance: Any, schema: Any, path: str = "$", _depth: int = 0) -> List[ValidationError]:
        errors: List[ValidationError] = []
        if _depth > self.max_depth:
            raise SchemaError(f"schema 递归深度超过 {self.max_depth}，疑似 $ref 环")
        if _depth == 0:
            self._root_schema = schema
        if schema is True or schema == {}:
            return errors
        if schema is False:
            return [ValidationError(path, "false-schema", "schema 恒假")]
        if not isinstance(schema, dict):
            return errors

        if "$ref" in schema:
            ref = schema["$ref"]
            if ref.startswith("#"):
                # 内部指针（#/...）：按 draft-07 语义对当前 schema 文档根解析，
                # 无需调用方提供 resolver。
                if self._root_schema is None:
                    raise SchemaError(f"内部 $ref 缺少文档根，无法解析: {ref}")
                target = _resolve_pointer(self._root_schema, ref)
            else:
                if self.resolver is None:
                    raise SchemaError(f"遇到跨文件 $ref 但没有提供 resolver: {ref}")
                target = self.resolver(ref)
            errors.extend(self.validate(instance, target, path, _depth + 1))

        errors.extend(self._check_type(instance, schema, path))
        errors.extend(self._check_values(instance, schema, path))
        errors.extend(self._check_container(instance, schema, path, _depth))
        errors.extend(self._check_combinators(instance, schema, path, _depth))
        return errors

    # ---- 各关键字族 ----
    def _check_type(self, instance: Any, schema: dict, path: str) -> List[ValidationError]:
        errors: List[ValidationError] = []
        if "type" in schema:
            types = schema["type"]
            wanted = types if isinstance(types, list) else [types]
            if not any(_matches_type(instance, t) for t in wanted):
                errors.append(
                    ValidationError(
                        path, "type", f"类型应为 {'/'.join(wanted)}，实际为 {_json_type_name(instance)}"
                    )
                )
        return errors

    def _check_values(self, instance: Any, schema: dict, path: str) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if "enum" in schema:
            if not any(_json_equal(instance, allowed) for allowed in schema["enum"]):
                errors.append(ValidationError(path, "enum", f"取值 {instance!r} 不在允许枚举 {schema['enum']} 中"))
        if "const" in schema:
            if not _json_equal(instance, schema["const"]):
                errors.append(ValidationError(path, "const", f"取值应为常量 {schema['const']!r}，实际 {instance!r}"))

        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                errors.append(ValidationError(path, "minLength", f"字符串长度 {len(instance)} < 最小长度 {schema['minLength']}"))
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errors.append(ValidationError(path, "maxLength", f"字符串长度 {len(instance)} > 最大长度 {schema['maxLength']}"))
            if "pattern" in schema and not re.search(schema["pattern"], instance):
                errors.append(ValidationError(path, "pattern", f"字符串不匹配正则 {schema['pattern']!r}: {instance!r}"))
            if "format" in schema and not _check_format(instance, schema["format"]):
                errors.append(ValidationError(path, "format", f"不符合 {schema['format']} 格式: {instance!r}"))

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(ValidationError(path, "minimum", f"{instance} < 最小值 {schema['minimum']}"))
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(ValidationError(path, "maximum", f"{instance} > 最大值 {schema['maximum']}"))
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                errors.append(ValidationError(path, "exclusiveMinimum", f"{instance} <= 排他下界 {schema['exclusiveMinimum']}"))
            if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
                errors.append(ValidationError(path, "exclusiveMaximum", f"{instance} >= 排他上界 {schema['exclusiveMaximum']}"))
            if "multipleOf" in schema and schema["multipleOf"]:
                quotient = instance / schema["multipleOf"]
                if abs(quotient - round(quotient)) > 1e-9:
                    errors.append(ValidationError(path, "multipleOf", f"{instance} 不是 {schema['multipleOf']} 的整数倍"))
        return errors

    def _check_container(self, instance: Any, schema: dict, path: str, depth: int) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if isinstance(instance, dict):
            props = schema.get("properties", {}) or {}
            pattern_props = schema.get("patternProperties", {}) or {}
            for key in schema.get("required", []) or []:
                if key not in instance:
                    errors.append(ValidationError(path, "required", f"缺少必填字段 {key!r}"))
            for key, value in instance.items():
                child = _join(path, key)
                matched = False
                if key in props:
                    matched = True
                    errors.extend(self.validate(value, props[key], child, depth + 1))
                for pattern, subschema in pattern_props.items():
                    if re.search(pattern, key):
                        matched = True
                        errors.extend(self.validate(value, subschema, child, depth + 1))
                if not matched and schema.get("additionalProperties") is False:
                    errors.append(ValidationError(child, "additionalProperties", f"不允许的额外字段 {key!r}"))
                elif not matched and isinstance(schema.get("additionalProperties"), dict):
                    errors.extend(self.validate(value, schema["additionalProperties"], child, depth + 1))

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                errors.append(ValidationError(path, "minItems", f"数组长度 {len(instance)} < 最小 {schema['minItems']}"))
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append(ValidationError(path, "maxItems", f"数组长度 {len(instance)} > 最大 {schema['maxItems']}"))
            if schema.get("uniqueItems") and len(instance) != len({json.dumps(i, sort_keys=True, ensure_ascii=False) for i in instance}):
                errors.append(ValidationError(path, "uniqueItems", "数组存在重复元素"))
            items = schema.get("items")
            if isinstance(items, dict):
                for index, item in enumerate(instance):
                    errors.extend(self.validate(item, items, _join(path, index), depth + 1))
            elif isinstance(items, list):
                for index, item in enumerate(instance):
                    if index < len(items):
                        errors.extend(self.validate(item, items[index], _join(path, index), depth + 1))
        return errors

    def _check_combinators(self, instance: Any, schema: dict, path: str, depth: int) -> List[ValidationError]:
        errors: List[ValidationError] = []

        for subschema in schema.get("allOf", []) or []:
            errors.extend(self.validate(instance, subschema, path, depth + 1))

        if "anyOf" in schema:
            sub_errors = [self.validate(instance, s, path, depth + 1) for s in schema["anyOf"]]
            if all(sub for sub in sub_errors):
                errors.append(ValidationError(path, "anyOf", "不满足 anyOf 中任何一支"))

        if "oneOf" in schema:
            passing = [i for i, s in enumerate(schema["oneOf"]) if not self.validate(instance, s, path, depth + 1)]
            if len(passing) != 1:
                errors.append(ValidationError(path, "oneOf", f"应恰好满足 oneOf 中一支，实际满足 {len(passing)} 支"))

        if "not" in schema:
            if not self.validate(instance, schema["not"], path, depth + 1):
                errors.append(ValidationError(path, "not", "不允许满足 not 分支"))

        if "if" in schema:
            condition_ok = not self.validate(instance, schema["if"], path, depth + 1)
            if condition_ok and "then" in schema:
                errors.extend(self.validate(instance, schema["then"], path, depth + 1))
            elif not condition_ok and "else" in schema:
                errors.extend(self.validate(instance, schema["else"], path, depth + 1))
        return errors


def validate(
    instance: Any,
    schema: Any,
    resolver: Optional[Callable[[str], Any]] = None,
) -> List[ValidationError]:
    """校验 ``instance`` 是否满足 ``schema``，返回全部错误（空列表即通过）。

    Args:
        instance: 待校验的 Python 对象（来自 JSON/YAML 解析）。
        schema: JSON Schema（dict）。
        resolver: 解析 ``$ref`` 的回调；``vocab.json#/x`` 这类跨文件引用需要它。

    Returns:
        ValidationError 列表；为空表示通过。

    Raises:
        SchemaError: schema 自身不可解析（例如无 resolver 遇到 $ref）。
    """
    return _Validator(resolver).validate(instance, schema)


def _resolve_pointer(document: Any, ref: str) -> Any:
    """解析 ``#/a/b`` 形式的内部 JSON Pointer（文档根引用）。

    只处理当前 schema 文档内部的指针；跨文件 ``file.json#/x`` 仍由 resolver 负责。
    """
    pointer = ref[1:] if ref.startswith("#") else ref
    current: Any = document
    if pointer:
        for raw_token in pointer.strip("/").split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and token in current:
                current = current[token]
            elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
                current = current[int(token)]
            else:
                raise SchemaError(f"$ref 指针无法解析: {ref}")
    return current


def make_file_resolver(base_dir: "str | Any") -> Callable[[str], Any]:
    """构造基于目录的 $ref 解析器。

    用于跨文件引用（``vocab.json#/x``）；文档内部指针（``#/...``）由校验器自动解析，
    无需本函数参与。

    Args:
        base_dir: schemas 所在目录（pathlib.Path 或字符串）。

    Returns:
        可传给 :func:`validate` 的 resolver。
    """
    from pathlib import Path

    root = Path(base_dir)

    def _resolve(ref: str) -> Any:
        if ref.startswith("#"):
            raise SchemaError(f"裸内部引用 {ref} 需要调用方自行展开")
        file_part, _, pointer = ref.partition("#")
        target_path = root / file_part
        if not target_path.exists():
            raise SchemaError(f"$ref 目标文件不存在: {target_path}")
        with target_path.open("r", encoding="utf-8") as handle:
            doc = json.load(handle)
        current: Any = doc
        if pointer:
            for raw_token in pointer.strip("/").split("/"):
                token = raw_token.replace("~1", "/").replace("~0", "~")
                if isinstance(current, dict) and token in current:
                    current = current[token]
                else:
                    raise SchemaError(f"$ref 指针无法解析: {ref}")
        return current

    return _resolve


def iter_errors(instance: Any, schema: Any, resolver: Optional[Callable[[str], Any]] = None) -> Iterable[ValidationError]:
    """:func:`validate` 的迭代器别名（便于流式消费）。"""
    yield from validate(instance, schema, resolver=resolver)
