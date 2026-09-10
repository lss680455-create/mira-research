"""jsonschema_lite：draft-07 子集校验器的单元测试。"""

import pytest

from mira.jsonschema_lite import SchemaError, iter_errors, make_file_resolver, validate


def errors(instance, schema, resolver=None):
    return validate(instance, schema, resolver=resolver)


def keywords(instance, schema):
    return sorted(err.keyword for err in errors(instance, schema))


# ---------------------------------------------------------------- type / values

def test_type_ok():
    assert errors("x", {"type": "string"}) == []
    assert errors(3, {"type": "integer"}) == []


def test_type_mismatch_reports_type_keyword():
    result = errors("x", {"type": "integer"})
    assert len(result) == 1
    assert result[0].keyword == "type"
    assert result[0].path == "$"


def test_bool_is_not_integer():
    assert errors(True, {"type": "integer"})


def test_integer_is_number():
    assert errors(3, {"type": "number"}) == []


def test_enum_hit_and_miss():
    schema = {"enum": ["a", "b"]}
    assert errors("a", schema) == []
    assert keywords("z", schema) == ["enum"]


def test_const():
    assert errors(1, {"const": 1}) == []
    assert keywords(2, {"const": 1}) == ["const"]


def test_pattern_and_length():
    assert errors("2026-04-14", {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}) == []
    assert keywords("26-4-1", {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}) == ["pattern"]
    assert keywords("", {"type": "string", "minLength": 1}) == ["minLength"]


def test_format_date():
    schema = {"type": "string", "format": "date"}
    assert errors("2026-04-14", schema) == []
    assert keywords("2026-13-01", schema) == ["format"]


# ---------------------------------------------------------------- containers

def test_required_reports_missing_field():
    result = errors({}, {"type": "object", "required": ["a"]})
    assert [e.keyword for e in result] == ["required"]
    assert "a" in result[0].message


def test_additional_properties_false():
    schema = {"type": "object", "properties": {"a": {}}, "additionalProperties": False}
    assert errors({"a": 1}, schema) == []
    result = errors({"a": 1, "b": 2}, schema)
    assert [e.keyword for e in result] == ["additionalProperties"]


def test_min_items_and_unique_items():
    schema = {"type": "array", "minItems": 1}
    assert keywords([], schema) == ["minItems"]
    assert errors([1], schema) == []
    uq = {"type": "array", "uniqueItems": True}
    assert errors([1, 1], uq) != []
    assert errors([1, 2], uq) == []


def test_nested_path_in_error():
    schema = {"type": "object", "properties": {"refresh": {"type": "object", "properties": {"stale_after": {"type": "string"}}}}}
    result = errors({"refresh": {"stale_after": 3}}, schema)
    assert result[0].path == "$.refresh.stale_after"


def test_array_item_path():
    schema = {"type": "array", "items": {"type": "integer"}}
    result = errors([1, "x"], schema)
    assert result[0].path == "$[1]"


# ---------------------------------------------------------------- combinators

def test_all_of_any_of_one_of_not():
    assert errors(3, {"allOf": [{"type": "integer"}, {"minimum": 1}]}) == []
    assert keywords(0, {"allOf": [{"type": "integer"}, {"minimum": 1}]}) == ["minimum"]
    assert errors("a", {"anyOf": [{"type": "string"}, {"type": "integer"}]}) == []
    assert keywords(True, {"anyOf": [{"type": "string"}, {"type": "number"}]}) == ["anyOf"]
    assert errors(1, {"oneOf": [{"type": "integer"}, {"type": "string"}]}) == []
    assert keywords(1, {"oneOf": [{"type": "integer"}, {"type": "number"}]}) == ["oneOf"]
    assert errors("x", {"not": {"type": "integer"}}) == []
    assert keywords(1, {"not": {"type": "integer"}}) == ["not"]


def test_if_then_else():
    schema = {
        "if": {"properties": {"t": {"const": "x"}}, "required": ["t"]},
        "then": {"required": ["a"]},
        "else": {"required": ["b"]},
    }
    assert errors({"t": "x", "a": 1}, schema) == []
    assert keywords({"t": "x"}, schema) == ["required"]
    assert errors({"t": "y", "b": 1}, schema) == []
    assert keywords({"t": "y"}, schema) == ["required"]


# ---------------------------------------------------------------- $ref

def test_local_ref_definitions():
    schema = {
        "definitions": {"positive": {"type": "integer", "minimum": 1}},
        "properties": {"n": {"$ref": "#/definitions/positive"}},
    }
    assert errors({"n": 2}, schema) == []
    assert keywords({"n": 0}, schema) == ["minimum"]


def test_file_resolver(tmp_path):
    (tmp_path / "defs.json").write_text('{"definitions": {"d": {"type": "string"}}}', encoding="utf-8")
    resolver = make_file_resolver(tmp_path)
    assert resolver("defs.json#/definitions/d") == {"type": "string"}


def test_unresolvable_ref_raises_schema_error():
    with pytest.raises(SchemaError):
        errors({}, {"$ref": "https://example.com/missing.json#/x"})


def test_iter_errors_is_lazy_generator():
    gen = iter_errors("x", {"type": "integer"})
    assert list(gen)[0].keyword == "type"


def test_unknown_keywords_are_ignored():
    # 未知关键字（例如 $comment / title / description）必须被静默忽略
    schema = {"$comment": "noise", "title": "t", "description": "d", "type": "string"}
    assert errors("ok", schema) == []
