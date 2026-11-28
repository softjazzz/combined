"""架构治理批次 3 回归测试：取材显式读取合同与失败阶段标记、冻结底层原语统一、科室规则 DB 503 收口。

纯离线测试（SQLite / 临时目录 / 并发线程 / AST），覆盖：
1. case_material_capture 不再依赖 walk_tb 函数名推断，校验边界显式标记 capture_stage="source_validation"
   （即使校验函数被包装/改名，日志阶段仍精确为 source_validation 且不含正文/凭据）；
2. 读取模块公开合同（assembly / current_view / emr_view / source_evidence_reader / sample_programmatic_evidence）
   与既有私有实现返回完全一致，且 AST 门禁禁止 case_material_capture 再回退读取这些私有属性；
3. 共享冻结存储原语 freeze_storage 的并发首次写入胜出、旧键/重启回读兼容、四模块共用同一底层原语且 AST 零重复；
4. department_qc_rules._resolve_qc_manager_scope 在意外 DB 故障时 fail-closed 返回 503。
"""

from __future__ import annotations

import ast
import concurrent.futures
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import connection as db_conn
from app.routers import department_qc_rules
from app.services import (
    automatic_material_scope,
    case_material_capture,
    case_material_snapshot,
    sample_programmatic_evidence,
)
from app.services.bundles import assembly, current_view, emr_view
from app.services.luxian_0609 import (
    antimicrobial_freeze,
    consultation_opinion_freeze,
    consultation_response_freeze,
    exam_analysis_freeze,
    freeze_storage,
    source_evidence_reader,
)

SERVICES_DIR = Path(__file__).resolve().parents[2] / "app" / "services"


# ---------------------------------------------------------------------------
# 1. 显式失败阶段标记（不依赖 traceback 函数名）与公开取材合同
# ---------------------------------------------------------------------------


def test_explicit_source_validation_stage_survives_wrapper_rename(caplog):
    """即使 validate_read_contract / validate_table_identity 被任意改名或转发，仍识别为 source_validation。"""
    def _renamed_validator_wrapper():
        return automatic_material_scope.validate_read_contract(
            {"read_only": True, "account_read_only": True}
        )

    with pytest.raises(KeyError) as caught:
        _renamed_validator_wrapper()

    assert getattr(caught.value, "capture_stage", None) == "source_validation"

    with caplog.at_level("ERROR", logger=case_material_capture.__name__):
        case_material_capture._log_capture_failure("source_read", caught.value)

    [record] = [r for r in caplog.records if r.name == case_material_capture.__name__]
    assert record.getMessage() == "material_capture_failed stage=source_validation code=unknown"


def test_validate_table_identity_tags_source_validation_stage():
    with pytest.raises(case_material_snapshot.MaterialSnapshotError) as caught:
        case_material_snapshot.validate_table_identity(
            "admission_record",
            ("institute_id", "patient_id", "visit_id"),
            ("H1", "P1", "V1"),
            [{"institute_id": "H2", "patient_id": "P1", "visit_id": "V1"}],
        )
    assert str(caught.value) == "material_identity_or_source_mismatch"
    assert caught.value.capture_stage == "source_validation"


def test_public_capture_contracts_match_owners():
    assert assembly.capture_material_limits() == assembly._material_limits_for_variants(
        scenes=tuple(assembly._SCENE_DOC_PRIORITY),
        domains=tuple(assembly._DOMAIN_DOC_PRIORITY),
    )
    assert assembly.default_source_schema() == assembly._default_source_schema()
    assert emr_view.DOMAIN_LOAD_ORDER == emr_view._DOMAIN_LOAD_ORDER
    assert sample_programmatic_evidence.programmatic_source_tables() == tuple(
        sample_programmatic_evidence._SOURCE_TABLES
    )
    catalog = source_evidence_reader.capture_source_catalog()
    assert catalog["native_source_keys"] == tuple(source_evidence_reader._NATIVE_SOURCE_FIELDS)
    assert catalog["snapshot_source_keys"] == tuple(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS)
    assert catalog["runtime_source_keys"] == (
        "surgery_record",
        "mr_surgery",
        "presurg_summary",
        "surgery_safecheck_record",
    )


def test_ast_guard_capture_uses_no_walk_tb_or_private_assembly_reader_internals():
    capture_path = SERVICES_DIR / "case_material_capture.py"
    src = capture_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(src, filename=str(capture_path))

    assert "walk_tb" not in src, "case_material_capture 不得通过 walk_tb 函数名推断失败阶段"

    forbidden_attrs = {
        "_default_source_schema",
        "_source_engine",
        "_material_limits_for_variants",
        "_SCENE_DOC_PRIORITY",
        "_DOMAIN_DOC_PRIORITY",
        "_select_records",
        "_NATIVE_SOURCE_FIELDS",
        "_SNAPSHOT_SOURCE_FIELDS",
        "_assemble_current_documents",
        "_DOMAIN_LOAD_ORDER",
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attrs:
            found.append(node.attr)
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
            "sample_programmatic_evidence"
        ):
            for alias in node.names:
                if alias.name == "_SOURCE_TABLES":
                    found.append("_SOURCE_TABLES")
    assert found == [], f"case_material_capture 禁止直接访问私有读取实现: {found}"


# ---------------------------------------------------------------------------
# 2. 冻结存储共享原语：并发写入、旧键兼容、重启回读、AST 零副本
# ---------------------------------------------------------------------------


def test_freeze_modules_share_single_primitive_implementations():
    for mod in (antimicrobial_freeze, exam_analysis_freeze):
        assert mod._path_lock is freeze_storage.path_lock
        assert mod._kernel_file_lock is freeze_storage.kernel_file_lock
        assert mod._replace_with_retry is freeze_storage.replace_with_retry
        assert mod._publish_once_with_kernel_lock is freeze_storage.publish_once_with_kernel_lock
        assert mod._is_valid_freeze_file is freeze_storage.is_valid_freeze_file

    for mod in (consultation_opinion_freeze, consultation_response_freeze):
        assert mod._path_lock is freeze_storage.path_lock
        assert mod._atomic_replace is freeze_storage.atomic_replace
        assert mod._resolve_case_scope is freeze_storage.resolve_case_scope
        assert mod._case_scope_hash is freeze_storage.case_scope_hash
        assert mod._freeze_stem is freeze_storage.freeze_stem


def test_freeze_storage_concurrent_publish_first_valid_writer_wins_and_reloads(tmp_path):
    target = tmp_path / "entry.json"

    def _writer(idx: int) -> None:
        tmp_file = tmp_path / f".tmp-{idx}.json"
        tmp_file.write_text(json.dumps({"winner": idx, "ok": True}), encoding="utf-8")
        try:
            freeze_storage.publish_once_with_kernel_lock(tmp_file, target)
        finally:
            tmp_file.unlink(missing_ok=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_writer, range(8)))

    assert freeze_storage.is_valid_freeze_file(target)
    first_payload = json.loads(target.read_text(encoding="utf-8"))
    assert first_payload["ok"] is True

    # 模拟进程重启后再次发布不会覆盖既有有效冻结文件
    later_tmp = tmp_path / ".tmp-later.json"
    later_tmp.write_text(json.dumps({"winner": 999, "ok": True}), encoding="utf-8")
    try:
        freeze_storage.publish_once_with_kernel_lock(later_tmp, target)
    finally:
        later_tmp.unlink(missing_ok=True)

    assert json.loads(target.read_text(encoding="utf-8")) == first_payload


def test_freeze_stem_preserves_legacy_visit_keys_and_scoped_keys():
    # 旧键：纯安全 visit_id 无作用域时保持原样，确保历史冻结文件可读
    assert freeze_storage.freeze_stem("V-2026-001") == "V-2026-001"
    # 带院区/患者作用域时固定生成确定性 16 位十六进制后缀
    scoped = freeze_storage.freeze_stem("V-2026-001", institute_id="H-01", patient_id="P-99")
    assert scoped.startswith("V-2026-001__")
    assert len(scoped.split("__", 1)[1]) == 16
    assert scoped == freeze_storage.freeze_stem("V-2026-001", institute_id="H-01", patient_id="P-99")
    # 含路径分隔符或单独 .. 的 visit_id 安全归一化并带 16 位哈希防碰撞
    traversal = freeze_storage.freeze_stem("../escape")
    assert "/" not in traversal and "\\" not in traversal and "__" in traversal
    assert freeze_storage.freeze_stem("..").startswith("visit__")


def test_ast_guard_no_duplicate_freeze_lock_or_scope_helpers():
    freeze_dir = SERVICES_DIR / "luxian_0609"
    forbidden = {
        "_path_lock",
        "_kernel_file_lock",
        "_replace_with_retry",
        "_publish_once_with_kernel_lock",
        "_atomic_replace",
        "_resolve_case_scope",
        "_case_scope_hash",
        "_freeze_stem",
    }
    offenders: list[tuple[str, str]] = []
    for name in (
        "antimicrobial_freeze.py",
        "exam_analysis_freeze.py",
        "consultation_opinion_freeze.py",
        "consultation_response_freeze.py",
    ):
        path = freeze_dir / name
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in forbidden:
                offenders.append((name, node.name))
    assert offenders == [], f"冻结领域模块不得重复定义底层锁/键原语: {offenders}"


# ---------------------------------------------------------------------------
# 3. department_qc_rules._resolve_qc_manager_scope DB 异常 fail-closed 503
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_factory",
    [
        lambda: OperationalError("SELECT 1", {}, Exception("connection refused")),
        lambda: SQLAlchemyError("db timeout"),
        lambda: RuntimeError("unexpected db failure"),
    ],
)
def test_department_qc_rules_scope_fails_closed_503_on_db_error(monkeypatch, error_factory):
    class _BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_bind(self):
            raise error_factory()

    monkeypatch.setattr(db_conn, "SessionLocal", lambda: _BrokenSession())
    with pytest.raises(HTTPException) as exc_info:
        department_qc_rules._resolve_qc_manager_scope(
            {"id": "u-admin", "roles": ["admin"], "institute_id": ""}
        )
    assert exc_info.value.status_code == 503


def test_department_qc_rules_scope_allows_empty_sqlite_table_fallback(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        assert department_qc_rules._resolve_qc_manager_scope(
            {"id": "u-bound", "roles": ["super_admin"], "institute_id": "H-1"}
        ) == (False, "H-1", "", "")
        assert department_qc_rules._resolve_qc_manager_scope(
            {"id": "u-global", "roles": ["super_admin"], "institute_id": ""}
        ) == (True, "", "", "")
    finally:
        engine.dispose()
