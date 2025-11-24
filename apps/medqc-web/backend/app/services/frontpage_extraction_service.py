from __future__ import annotations

"""
病案首页自动生成服务（骨架实现）

当前版本：
- 不调用真实 LLM，仅使用已有 demo JSON 数据构造 FrontPageDraft
- 作为 /api/v1/frontpage/auto-generate-draft 的后端支撑

后续可以在此文件中逐步接入：
- 文书获取逻辑（根据 visit_id 调用 records / medical_documents API）
- LLM 抽取逻辑（按模块拆 prompt，生成 FrontPageDraft）
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from ..schemas.frontpage import FrontPageDraft


class FrontPageExtractionService:
    """病案首页抽取服务（仅骨架 + demo 数据）"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        # base_dir 指向 backend/app 目录，用于定位 data/frontpage_demo_case.json
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = base_dir
        self.demo_data_path = self.base_dir / "data" / "frontpage_demo_case.json"

    async def generate_draft_from_visit(self, visit_id: str) -> FrontPageDraft:
        """
        根据住院 ID 生成首页草稿（当前版本：直接返回 demo 数据）

        说明：
        - 目前不解析真实病历，仅作为接口骨架和前端联调使用。
        - 后续可在此处：
          1. 根据 visit_id 拉取全病历文书；
          2. 调用 LLM 抽取各模块字段；
          3. 组装为 FrontPageDraft 返回。
        """
        return await self._load_demo_frontpage()

    async def generate_draft_from_documents(
        self, documents: List[Dict[str, Any]]
    ) -> FrontPageDraft:
        """
        根据传入的文书列表生成首页草稿（当前版本：忽略文书，返回 demo 数据）

        说明：
        - 参数保留为 future use，方便后续直接对接真实文书。
        """
        _ = documents  # 占位，避免未使用变量告警
        return await self._load_demo_frontpage()

    async def _load_demo_frontpage(self) -> FrontPageDraft:
        """
        从 demo JSON 文件加载 FrontPageDraft
        """
        if not self.demo_data_path.exists():
            raise FileNotFoundError(
                f"示例数据文件不存在: {self.demo_data_path}，请确认 frontpage_demo_case.json 是否存在。"
            )

        with self.demo_data_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        raw_frontpage = payload.get("frontpage") or {}
        if not raw_frontpage:
            raise ValueError("示例数据中缺少 frontpage 字段")

        # 兼容 demo JSON 中的 diagnosis_and_procedures 结构，
        # 将其拆分为 FrontPageDraft 需要的 diagnoses + procedures 两块。
        diag_proc = raw_frontpage.get("diagnosis_and_procedures") or {}

        # 诊断部分
        ed = diag_proc.get("ed_diagnosis") or []
        ed_texts = [item.get("text", "") for item in ed if isinstance(item, dict)]

        main_diag = diag_proc.get("discharge_main_diagnosis") or {}
        other_diags = diag_proc.get("discharge_other_diagnoses") or []
        other_texts = [
            item.get("text", "") for item in other_diags if isinstance(item, dict)
        ]

        diagnoses = {
            "ed_diagnosis_texts": ed_texts,
            "discharge_main_diagnosis_text": main_diag.get("text"),
            "discharge_other_diagnoses_texts": other_texts,
            "admission_condition": main_diag.get("admission_condition"),
        }

        # 手术部分
        main_proc = diag_proc.get("main_procedure") or {}
        procedures = {
            "main_procedure_text": main_proc.get("name"),
            "main_procedure_date": main_proc.get("date"),
            "main_procedure_level": main_proc.get("level"),
            "surgeon_name": main_proc.get("surgeon_name"),
            "assistant1_name": main_proc.get("assistant1_name"),
            "assistant2_name": main_proc.get("assistant2_name"),
            "anesthesia_method": main_proc.get("anesthesia_method"),
            "anesthetist_name": main_proc.get("anesthetist_name"),
            "incision_healing_grade": main_proc.get("incision_healing_grade"),
        }

        # 将拆分后的结构合并回 frontpage 数据，用于 Pydantic 验证
        frontpage_data = {
            **raw_frontpage,
            "diagnoses": diagnoses,
            "procedures": procedures,
        }

        return FrontPageDraft.model_validate(frontpage_data)


# 提供一个单例风格的访问方式，方便在路由中复用
default_frontpage_service = FrontPageExtractionService()
