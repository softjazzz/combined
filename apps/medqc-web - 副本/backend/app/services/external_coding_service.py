
"""
ICD 编码提取服务

优先使用本地 ICD 编码库进行匹配（速度快、无网络依赖），
当本地匹配不到时可选择回退到远程 API 服务。

本地编码库数据来源：
- ICD-10 国临版（诊断编码）
- ICD-9-CM-3（手术操作编码）
"""

from typing import Dict, Any, Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class ExternalCodingService:
    """ICD 编码提取服务（本地优先）"""

    # 远程服务作为备选（当前已下线）
    REMOTE_BASE_URL = os.getenv("EXTERNAL_CODING_URL", "http://122.51.111.253:8002")
    USE_REMOTE = os.getenv("EXTERNAL_CODING_USE_REMOTE", "false").lower() == "true"
    MAX_SECONDS = float(os.getenv("EXTERNAL_CODING_MAX_SECONDS", "25"))

    async def extract_coding(self, medical_text: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        从病历文本中提取诊断和手术的 ICD 编码

        优先使用本地 ICD 编码库，无需网络请求。

        Args:
            medical_text: 病历文本（当前未直接使用，编码在 LLM 抽取后由 local_icd_service 匹配）
            patient_context: 患者信息 {gender, age, ...}

        Returns:
            Dict: 编码结果，包含 coding_data 字段
        """
        try:
            return await self._local_coding(medical_text, patient_context)
        except Exception as e:
            logger.warning(f"本地编码查询失败: {e}")
            if self.USE_REMOTE:
                logger.info("尝试回退到远程编码服务...")
                return await self._remote_coding(medical_text, patient_context)
            # 本地失败且不使用远程时，返回空结果（不阻断主流程）
            return {"coding_data": {}, "source": "empty", "error": str(e)}

    async def _local_coding(self, medical_text: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用本地 ICD 编码库进行编码匹配"""
        from .local_icd_service import lookup_diagnosis_code, lookup_procedure_code

        # 本地编码服务的工作方式：
        # 它在 frontpage_extraction_service.py 的流式提取末尾已经被调用了
        # （resolve_diagnosis_codes / resolve_procedure_codes）
        # 这里我们返回一个空的 coding_data，让流式流程中后续的
        # local ICD resolve 步骤来完成实际编码工作

        logger.info("使用本地 ICD 编码库（跳过远程服务）")

        # 返回一个标记，告诉调用方编码将由本地 ICD 服务在后续步骤中完成
        return {
            "coding_data": {},
            "source": "local_icd",
            "message": "编码将由本地 ICD 编码库在后续步骤中完成"
        }

    async def _remote_coding(self, medical_text: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        """回退到远程编码服务（仅在 USE_REMOTE=true 时使用）"""
        import httpx
        import uuid
        import asyncio

        async def run():
            job_id = await self._submit_job(medical_text, patient_context)
            if not job_id:
                raise Exception("Failed to submit coding job")
            return await self._poll_result(job_id)

        try:
            return await asyncio.wait_for(run(), timeout=self.MAX_SECONDS)
        except asyncio.TimeoutError as e:
            raise TimeoutError("External coding service timed out") from e

    async def _submit_job(self, text: str, context: dict) -> Optional[str]:
        import httpx
        import uuid

        async with httpx.AsyncClient(trust_env=False) as client:
            try:
                payload = {
                    "request_id": f"req_{uuid.uuid4().hex[:8]}",
                    "document_type": "admission_note",
                    "text_content": text,
                    "patient_context": context,
                    "coding_mode": "default"
                }

                resp = await client.post(
                    f"{self.REMOTE_BASE_URL}/api/v1/coding/extract",
                    json=payload,
                    timeout=30
                )

                if resp.status_code == 202:
                    data = resp.json()
                    return data.get("data", {}).get("job_id")
                else:
                    logger.error(f"Submit job failed: {resp.status_code} - {resp.text}")
                    return None
            except Exception as e:
                logger.error(f"Error submitting job: {e}")
                raise

    async def _poll_result(self, job_id: str, max_retries: int = 12, interval: int = 2) -> Dict[str, Any]:
        import httpx
        import asyncio

        async with httpx.AsyncClient(trust_env=False) as client:
            for i in range(max_retries):
                try:
                    await asyncio.sleep(interval)
                    resp = await client.get(
                        f"{self.REMOTE_BASE_URL}/api/v1/coding/jobs/{job_id}",
                        timeout=6
                    )

                    if resp.status_code in (200, 422):
                        data = resp.json()
                        if "data" in data:
                            return data["data"]

                    if resp.status_code not in (200, 202, 422):
                        logger.warning(f"Polling job {job_id} status: {resp.status_code}")

                except Exception as e:
                    logger.warning(f"Error polling job {job_id}: {e}")

            raise TimeoutError("Coding job polling timed out")


# 单例
external_coding_service = ExternalCodingService()

def get_external_coding_service() -> ExternalCodingService:
    return external_coding_service
