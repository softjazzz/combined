"""结算清单组装服务的跨机构数据隔离测试。

契约（与主 Agent 约定）：

- ``generate(patient_id, visit_id, frontpage_draft=None, db=None, institute_id=None)``
  以 ``institute_id`` 作为尾参。
- 现代模式（显式传入 ``institute_id``）：``cdm.mr`` / ``cdm.mr_surgery`` /
  ``cdm.medical_insurance_settlement`` / ``cdm.mr_icu`` 的读取必须按「机构 + 患者 + 就诊」过滤。
- 现代模式下 mr 无行 / SQL 读取报错 / 未提供 db 必须失败关闭：抛出
  ``SettlementAssemblyUnavailableError(ValueError)``。不接受「显式失败结果」或空草稿；
  即使调用方传了 ``frontpage_draft``，也不得跳过 cdm.mr 身份与取数校验。
- 现代模式下传入非空 ``frontpage_draft`` 一律抛 ``SettlementAssemblyUnavailableError``：
  现有链路没有 frontpage_draft 的可信机构合同，防止 mr 校验后仍混入越权 A 源；
  空草稿（``None`` / ``{}``）视为未提供。
- 显式传入无效机构号（``""`` / ``" "`` / ``"   "`` / 制表符等空白值）必须报错，
  不得悄悄回退两键 legacy 查询；只有 ``institute_id is None``（未提供）才走旧口径。
- 现代模式结果携带 ``institute_id``。
- 旧模式（``institute_id is None``）保持兼容，旧调用方式仍能生成草稿。

反例构造：A/B 两个机构写入同一 patient_id + visit_id，并交换插入顺序各跑一遍，
验证组装结果始终跟随请求机构，不因物理行顺序而混读。

不连接任何真实数据库：内存 SQLite + ATTACH ``cdm`` schema 伪 CDM 表，
表结构按服务实际使用的裸 SQL 列裁剪。

运行方式（不加载根 conftest，避免连库）::

    $env:DATABASE_URL="postgresql://invalid:invalid@127.0.0.1:1/nonexistent"
    python -m pytest tests/unit/test_settlement_assembly_identity.py --noconftest
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List

import pytest
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services.settlement_assembly_service import SettlementAssemblyService


PATIENT_ID = "P-2026-0001"
VISIT_ID = "V-2026-0001"

INSTITUTE_A = "hospital-a"
INSTITUTE_B = "hospital-b"

TAG_BY_INSTITUTE = {INSTITUTE_A: "A", INSTITUTE_B: "B"}


# ============================================================
# 伪 CDM 表（cdm schema）
# ============================================================

_CDM_METADATA = MetaData(schema="cdm")

MR = Table(
    "mr",
    _CDM_METADATA,
    Column("institute_id", String(100), primary_key=True),
    Column("patient_id", String(100), primary_key=True),
    Column("visit_id", String(100), primary_key=True),
    Column("name", String(100)),
    Column("sex", String(100)),
    Column("age_year", String(100)),
    Column("id_card_no", String(100)),
    Column("mr_no", String(100)),
    Column("institute_county_desc", String(100)),
    Column("institute_code", String(100)),
)

MR_SURGERY = Table(
    "mr_surgery",
    _CDM_METADATA,
    Column("institute_id", String(100), primary_key=True),
    Column("patient_id", String(100), primary_key=True),
    Column("visit_id", String(100), primary_key=True),
    Column("surgery_id", String(100), primary_key=True),
    Column("main_surgery_sign", String(10)),
    Column("surgery_name", String(200)),
    Column("surgery_code", String(100)),
    Column("surgeon_physician_code", String(100)),
)

MEDICAL_INSURANCE_SETTLEMENT = Table(
    "medical_insurance_settlement",
    _CDM_METADATA,
    Column("institute_id", String(100), primary_key=True),
    Column("patient_id", String(100), primary_key=True),
    Column("visit_id", String(100), primary_key=True),
    Column("patient_insurance_no", String(100)),
    Column("business_serial_no", String(100)),
    Column("settlement_status", String(100)),
)

MR_ICU = Table(
    "mr_icu",
    _CDM_METADATA,
    Column("institute_id", String(100), primary_key=True),
    Column("patient_id", String(100), primary_key=True),
    Column("visit_id", String(100), primary_key=True),
    Column("icu_id", String(100), primary_key=True),
    Column("icu_type", String(100)),
    Column("icu_period", String(50)),
    Column("icu_start_datetime", DateTime),
)

_CDM_TABLES = [MR, MR_SURGERY, MEDICAL_INSURANCE_SETTLEMENT, MR_ICU]


def _new_engine() -> Engine:
    """构造内存 SQLite 引擎，并挂载 ``cdm`` schema 与四张伪 CDM 表。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
    with engine.begin() as conn:
        _CDM_METADATA.create_all(conn, tables=_CDM_TABLES)
    return engine


def _seed(engine: Engine, institutes: List[str]) -> None:
    """按给定顺序写入机构数据，用于验证物理行顺序不影响读取结果。"""
    with engine.begin() as conn:
        for institute_id in institutes:
            tag = TAG_BY_INSTITUTE[institute_id]
            conn.execute(MR.insert().values(
                institute_id=institute_id,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                name=f"患者-{tag}",
                sex="男",
                age_year="48",
                id_card_no=f"ID-{tag}",
                mr_no=f"MR-{tag}",
                institute_county_desc=f"{tag}医院",
                institute_code=f"CODE-{tag}",
            ))
            conn.execute(MR_SURGERY.insert().values(
                institute_id=institute_id,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                surgery_id=f"S-{tag}",
                main_surgery_sign="1",
                surgery_name=f"手术-{tag}",
                surgery_code=f"9-{tag}",
                surgeon_physician_code=f"SURG-{tag}",
            ))
            conn.execute(MEDICAL_INSURANCE_SETTLEMENT.insert().values(
                institute_id=institute_id,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                patient_insurance_no=f"INS-{tag}",
                business_serial_no=f"BS-{tag}",
                settlement_status=f"STATUS-{tag}",
            ))
            conn.execute(MR_ICU.insert().values(
                institute_id=institute_id,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                icu_id=f"ICU-{tag}",
                icu_type=f"ICUTYPE-{tag}",
                icu_period="24",
            ))


def _iter_string_leaves(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_string_leaves(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_string_leaves(item)


def _assert_institute_payload(result: Dict[str, Any], institute_id: str) -> None:
    """结果必须整份来自请求机构，不得混入对方案例。"""
    tag = TAG_BY_INSTITUTE[institute_id]
    other_tag = "B" if tag == "A" else "A"

    assert result["institute_id"] == institute_id, (
        f"结果 institute_id 应为 {institute_id}: {result['institute_id']!r}"
    )

    # cdm.mr 表
    assert result["patient_name"] == f"患者-{tag}", (
        f"mr.name 跨机构混读: 期望患者-{tag}, 实得 {result['patient_name']!r}"
    )
    assert result["patient_id_card"] == f"ID-{tag}"
    assert result["mr_no"] == f"MR-{tag}"
    assert result["designated_medical_institution"] == f"{tag}医院"
    assert result["institution_code"] == f"CODE-{tag}"

    # cdm.medical_insurance_settlement 表
    assert result["business_serial_no"] == f"BS-{tag}", (
        f"结算清单跨机构混读: 期望 BS-{tag}, 实得 {result['business_serial_no']!r}"
    )
    assert result["insurance_no"] == f"INS-{tag}"
    assert result["settlement_status"] == f"STATUS-{tag}"

    # cdm.mr_surgery 表
    assert result["surgeon_physician_code"] == f"SURG-{tag}", (
        f"主手术跨机构混读: 期望 SURG-{tag}, 实得 {result['surgeon_physician_code']!r}"
    )

    # cdm.mr_icu 表
    icu_records = result["icu_records"]
    assert len(icu_records) == 1, f"ICU 明细应只含本机构 1 条: {icu_records!r}"
    assert icu_records[0]["icu_type"] == f"ICUTYPE-{tag}", (
        f"ICU 明细跨机构混读: {icu_records!r}"
    )

    # 对方案例的标识不得出现在任何可见字符串里
    for text_value in _iter_string_leaves(result):
        assert f"-{other_tag}" not in text_value, (
            f"结果混入 {other_tag} 机构数据: {text_value!r}"
        )


def _unavailable_error_type() -> type:
    """现代模式失败关闭的异常类型。

    契约约定为 ``SettlementAssemblyUnavailableError(ValueError)``；服务层尚未落地该符号时
    退化为 ``ValueError``，让其余用例仍可独立收集运行，而不是整文件 collection error。
    """
    from app.services import settlement_assembly_service as module

    error_type = getattr(module, "SettlementAssemblyUnavailableError", None)
    if isinstance(error_type, type) and issubclass(error_type, Exception):
        return error_type
    return ValueError


def _assert_fail_closed(service: SettlementAssemblyService, **kwargs: Any) -> None:
    """现代模式 mr 无行 / SQL 失败 / 无 db 必须失败关闭。

    只接受抛异常；任何返回值（显式失败结果、``is_draft`` 空草稿）都算失败。
    """
    with pytest.raises(_unavailable_error_type()):
        service.generate(**kwargs)


class _ExplodingSession:
    """模拟 CDM 读取异常（例如连接失败），用于验证失败关闭。"""

    def execute(self, *args: Any, **kwargs: Any) -> Any:  # noqa: D102 - 测试替身
        raise RuntimeError("simulated cdm read failure")


@pytest.fixture
def svc() -> SettlementAssemblyService:
    return SettlementAssemblyService()


# ============================================================
# 现代模式：跨机构隔离
# ============================================================

class TestModernModeInstituteIsolation:

    @pytest.mark.parametrize("order", [["A", "B"], ["B", "A"]], ids=["ab", "ba"])
    def test_reads_only_requested_institute(self, svc, order):
        """同一 patient+visit 的两机构数据，交换插入顺序都要读到请求机构。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A if tag == "A" else INSTITUTE_B for tag in order])

        with Session(engine) as db:
            result_a = svc.generate(PATIENT_ID, VISIT_ID, None, db, institute_id=INSTITUTE_A)
            result_b = svc.generate(PATIENT_ID, VISIT_ID, None, db, institute_id=INSTITUTE_B)

        _assert_institute_payload(result_a, INSTITUTE_A)
        _assert_institute_payload(result_b, INSTITUTE_B)

    def test_result_carries_institute_id(self, svc):
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A, INSTITUTE_B])

        with Session(engine) as db:
            result = svc.generate(
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                db=db,
                institute_id=INSTITUTE_B,
            )

        assert result["institute_id"] == INSTITUTE_B

    def test_modern_mode_without_draft_reads_b_class_for_requested_institute(self, svc):
        """现代模式未带草稿时，B 类补充必须来自请求机构。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A, INSTITUTE_B])

        with Session(engine) as db:
            result = svc.generate(
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                db=db,
                institute_id=INSTITUTE_B,
            )

        assert result["institute_id"] == INSTITUTE_B
        assert result["business_serial_no"] == "BS-B"
        assert result["patient_name"] == "患者-B"


# ============================================================
# 现代模式：失败关闭
# ============================================================

class TestModernModeFailClosed:

    def test_unavailable_error_is_value_error(self):
        """失败关闭异常类型约定：``SettlementAssemblyUnavailableError(ValueError)``。"""
        from app.services import settlement_assembly_service as module

        error_type = getattr(module, "SettlementAssemblyUnavailableError", None)
        assert isinstance(error_type, type), "服务层必须定义 SettlementAssemblyUnavailableError"
        assert issubclass(error_type, ValueError)

    def test_missing_mr_row_raises(self, svc):
        """mr 无行必须抛异常，不得退回空草稿。"""
        engine = _new_engine()

        with Session(engine) as db:
            _assert_fail_closed(
                svc,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft=None,
                db=db,
                institute_id=INSTITUTE_A,
            )

    def test_sibling_institute_data_raises(self, svc):
        """库里只有 B 机构数据时，请求 A 机构必须抛异常，不得空草稿。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_B])

        with Session(engine) as db:
            _assert_fail_closed(
                svc,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft=None,
                db=db,
                institute_id=INSTITUTE_A,
            )

    def test_sql_error_raises(self, svc):
        """CDM 读取异常必须抛异常，不能被吞掉后退回草稿。"""
        _assert_fail_closed(
            svc,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            frontpage_draft=None,
            db=_ExplodingSession(),
            institute_id=INSTITUTE_A,
        )

    def test_missing_db_raises(self, svc):
        """现代模式未提供 db 时不得静默用空 SQL 数据组装草稿。"""
        _assert_fail_closed(
            svc,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            frontpage_draft=None,
            db=None,
            institute_id=INSTITUTE_A,
        )


# ============================================================
# 现代模式：拒绝无可信机构合同的 frontpage_draft
# ============================================================

class TestModernModeRejectsBlankInstituteId:
    """显式传入无效机构号（空串 / 空白）必须报错，不得悄悄回退两键 legacy 查询。"""

    BLANKS = ["", " ", "   ", "\t"]
    BLANK_IDS = ["empty", "1-space", "3-spaces", "tab"]

    @pytest.mark.parametrize("blank", BLANKS, ids=BLANK_IDS)
    def test_blank_institute_id_raises(self, svc, blank):
        """legacy 两键查询本可命中 A 行，所以这里必须抛异常而不是产出草稿。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A])

        with Session(engine) as db:
            _assert_fail_closed(
                svc,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft=None,
                db=db,
                institute_id=blank,
            )

    @pytest.mark.parametrize("blank", BLANKS, ids=BLANK_IDS)
    def test_blank_institute_id_raises_even_with_db_missing(self, svc, blank):
        """未提供 db 时也必须按「显式指定机构」处理并报错。"""
        _assert_fail_closed(
            svc,
            patient_id=PATIENT_ID,
            visit_id=VISIT_ID,
            frontpage_draft=None,
            db=None,
            institute_id=blank,
        )


class TestModernModeRejectsUntrustedDraft:
    """现有链路没有 frontpage_draft 的可信机构合同，现代路径一律拒绝非空草稿。"""

    UNTRUSTED_DRAFT: Dict[str, Any] = {"basic_info": {"patient_name": "越权-甲"}}

    def test_non_empty_draft_rejected_even_when_mr_exists(self, svc):
        """mr 校验通过也不能放过外部注入的 A 源草稿。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_B])

        with Session(engine) as db:
            _assert_fail_closed(
                svc,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft=dict(self.UNTRUSTED_DRAFT),
                db=db,
                institute_id=INSTITUTE_B,
            )

    def test_non_empty_draft_rejected_when_mr_missing(self, svc):
        engine = _new_engine()

        with Session(engine) as db:
            _assert_fail_closed(
                svc,
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft=dict(self.UNTRUSTED_DRAFT),
                db=db,
                institute_id=INSTITUTE_A,
            )

    def test_empty_draft_is_treated_as_absent(self, svc):
        """``{}`` 不算非空草稿，现代路径按未提供处理，B 类补充仍按机构过滤。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_B])

        with Session(engine) as db:
            result = svc.generate(
                patient_id=PATIENT_ID,
                visit_id=VISIT_ID,
                frontpage_draft={},
                db=db,
                institute_id=INSTITUTE_B,
            )

        assert result["is_draft"] is True
        assert result["institute_id"] == INSTITUTE_B
        assert result["patient_name"] == "患者-B"


# ============================================================
# 旧模式兼容
# ============================================================

class TestLegacyModeCompatibility:

    def test_legacy_call_without_db_still_returns_draft(self, svc):
        """旧调用（无 institute_id、无 db）保持兼容，仍返回首页生成草稿。"""
        result = svc.generate(patient_id="p001", visit_id="v001")

        assert result["is_draft"] is True
        assert result["data_source"] == "generated_from_frontpage"
        assert result["patient_id"] == "p001"
        assert result["visit_id"] == "v001"

    def test_legacy_positional_call_keeps_signature(self, svc):
        """旧 4 参位置调用（patient, visit, draft, db）不得因新增尾参而破坏。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A, INSTITUTE_B])

        with Session(engine) as db:
            result = svc.generate(PATIENT_ID, VISIT_ID, None, db)

        assert result["is_draft"] is True
        assert result["data_source"] == "generated_from_frontpage"
        assert result["patient_id"] == PATIENT_ID
        assert result["visit_id"] == VISIT_ID
        # 旧模式不约束机构过滤语义，但必须仍能读出 mr 病例
        assert result["patient_name"] in {"患者-A", "患者-B"}

    def test_legacy_mode_with_frontpage_draft(self, svc):
        """旧模式显式注入草稿时行为不变。"""
        engine = _new_engine()
        _seed(engine, [INSTITUTE_A])
        draft = {"basic_info": {"patient_name": "旧模式张三"}}

        with Session(engine) as db:
            result = svc.generate(PATIENT_ID, VISIT_ID, draft, db)

        assert result["patient_name"] == "旧模式张三"
        assert result["is_draft"] is True
