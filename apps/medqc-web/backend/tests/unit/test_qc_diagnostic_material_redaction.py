"""合成材料引用的脱敏重建；不读取数据库和真实病历。"""
from types import MappingProxyType
from pathlib import Path
import os
import subprocess
import sys

import pytest

from app.services.luxian_0609.evidence_material import _build_material_document_rows
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.material_redaction import sanitize_material_sources
from app.services.qc_diagnostics.sanitization import PayloadSanitizer


def test_actual_material_rebuild_has_no_network_or_database_io(tmp_path):
    script = '''
import sys
attempts = []
def audit(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'sqlite3.connect'}:
        attempts.append(event)
        raise RuntimeError('external_io_forbidden')
sys.addaudithook(audit)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.qc_diagnostics.material_redaction import sanitize_material_sources
from app.services.qc_diagnostics.sanitization import PayloadSanitizer
source = SnapshotSourceRows.create(source_key='admission_record', rows=({'record_content': None},), truncated=False, limit_rows=1)
result = sanitize_material_sources({'admission_record': source}, sanitizer=PayloadSanitizer(identities=[], allowed_fields=frozenset({'record_content'}), date_shift_days=7))
assert result.sources['admission_record'].rows[0]['record_content'] is None
assert not attempts, attempts
print('offline_material_rebuild_ok')
'''
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2]), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "offline_material_rebuild_ok"


def sanitizer():
    return PayloadSanitizer(identities=[], allowed_fields=frozenset({
        "patient_name", "content", "document_id", "value",
    }), date_shift_days=7)


def source(rows, *, key="admission_record", truncated=False, limit=500):
    return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=truncated, limit_rows=limit)


def test_250_rows_rebuild_by_row_identity_after_sort_changes(monkeypatch):
    engine = sanitizer()
    # 固定匿名标识使 document_id 的排序完全反转，确定性暴露错误的 refs zip。
    monkeypatch.setattr(engine, "_alias", lambda raw: str(9999999 - int(raw)))
    original = source([{"document_id": str(1000000 + index), "value": index} for index in range(250)])
    result = sanitize_material_sources({original.source_key: original}, sanitizer=engine)
    old = _build_material_document_rows(original.source_key, original.rows)
    new = _build_material_document_rows(original.source_key, result.sources[original.source_key].rows)
    assert [row["value"] for _, row in old] != [row["value"] for _, row in new]
    by_value = {row["value"]: ref for ref, row in new}
    assert result.remap_document_refs(tuple(ref for ref, _ in old)) == tuple(by_value[row["value"]] for _, row in old)
    assert original.rows[0]["document_id"] == "1000000"
    assert len(set(result.remap_document_refs(tuple(ref for ref, _ in old)))) == 250


def test_duplicate_same_object_preserves_occurrence_order_and_repeated_references():
    row = MappingProxyType({"patient_name": "合成姓名", "content": None, "value": ""})
    original = SnapshotSourceRows("admission_record", (row, row), True, 2)
    result = sanitize_material_sources({"admission_record": original}, sanitizer=sanitizer())
    refs = tuple(ref for ref, _ in _build_material_document_rows("admission_record", original.rows))
    newrefs = tuple(ref for ref, _ in _build_material_document_rows("admission_record", result.sources["admission_record"].rows))
    assert result.remap_document_refs((refs[1], refs[0], refs[1])) == (newrefs[1], newrefs[0], newrefs[1])
    clean = result.sources["admission_record"]
    assert clean.truncated is True and clean.limit_rows == 2
    assert clean.rows[0]["content"] is None and clean.rows[0]["value"] == ""
    assert "absent" not in clean.rows[0]
    assert "合成姓名" not in repr(result) and refs[0] not in repr(result)
    with pytest.raises(TypeError):
        result.sources["new"] = clean


def test_cross_source_identity_is_collected_before_any_row_is_transformed():
    sources = {"admission_record": source([{"content": "合成姓名"}]),
               "daily_course_record": source([{"patient_name": "合成姓名"}], key="daily_course_record")}
    result = sanitize_material_sources(sources, sanitizer=sanitizer())
    assert result.sources["admission_record"].rows[0]["content"] == result.sources["daily_course_record"].rows[0]["patient_name"]
    assert sources["admission_record"].rows[0]["content"] == "合成姓名"


@pytest.mark.parametrize("refs", [("a" * 64,), ("../private",), (None,), ["a" * 64]])
def test_dangling_or_invalid_references_fail_closed(refs):
    result = sanitize_material_sources({}, sanitizer=sanitizer())
    with pytest.raises(DiagnosticPackageError):
        result.remap_document_refs(refs)


@pytest.mark.parametrize("sources", [
    {"unknown": SnapshotSourceRows("unknown", (), False, 1)},
    {"admission_record": source([], key="daily_course_record")},
    {"admission_record": SnapshotSourceRows("admission_record", (), True, 1)},
    {"admission_record": SnapshotSourceRows("admission_record", ({}, {}), False, 1)},
    {" Admission_Record ": source([])},
])
def test_invalid_source_contract_is_rejected(sources):
    with pytest.raises(DiagnosticPackageError):
        sanitize_material_sources(sources, sanitizer=sanitizer())


def test_empty_source_is_preserved():
    result = sanitize_material_sources({"admission_record": source([])}, sanitizer=sanitizer())
    assert result.sources["admission_record"].rows == ()
    assert result.remap_document_refs(()) == ()


def test_source_input_order_nested_values_and_original_data_are_preserved():
    raw = [{"document_id": "9999999", "value": {"content": [None, "", "合成姓名"]}},
           {"document_id": "1111111", "patient_name": "合成姓名"}]
    original = source(raw)
    result = sanitize_material_sources({"admission_record": original}, sanitizer=sanitizer())
    clean = result.sources["admission_record"].rows
    assert "value" in clean[0] and "patient_name" in clean[1]
    assert clean[0]["value"]["content"][:2] == [None, ""]
    assert clean[0]["value"]["content"][2] == clean[1]["patient_name"]
    assert raw[0]["value"]["content"][2] == "合成姓名"
    assert not hasattr(result, "__dict__")


def test_custom_row_value_is_rejected_before_hash_can_invoke_repr():
    class Unsafe:
        def __str__(self):
            pytest.fail("不得在验证前运行自定义 __str__")
    raw = SnapshotSourceRows("admission_record", ({"value": Unsafe()},), False, 1)
    with pytest.raises(DiagnosticPackageError):
        sanitize_material_sources({"admission_record": raw}, sanitizer=sanitizer())


def test_row_and_reference_resource_limits_are_enforced():
    raw = SnapshotSourceRows("admission_record", ({},) * 10001, False, 10001)
    with pytest.raises(DiagnosticPackageError):
        sanitize_material_sources({"admission_record": raw}, sanitizer=sanitizer())
    result = sanitize_material_sources({}, sanitizer=sanitizer())
    with pytest.raises(DiagnosticPackageError):
        result.remap_document_refs(("a" * 64,) * 10001)


def test_custom_source_mapping_is_rejected_without_iterating():
    class Unsafe(dict):
        def items(self):
            pytest.fail("不得迭代自定义映射")
    with pytest.raises(DiagnosticPackageError):
        sanitize_material_sources(Unsafe(), sanitizer=sanitizer())
