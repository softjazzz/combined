
from typing import Dict, Any, Optional
import httpx
import uuid
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

class ExternalCodingService:
    BASE_URL = "http://122.51.111.253:8002"
    MAX_SECONDS = float(os.getenv("EXTERNAL_CODING_MAX_SECONDS", "25"))
    
    async def extract_coding(self, medical_text: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用第三方 ICD 编码提取服务
        
        Args:
            medical_text: 病历文本
            patient_context: 患者信息 {gender, age, ...}
            
        Returns:
            Dict: 编码结果
        """
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
                    f"{self.BASE_URL}/api/v1/coding/extract",
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
        async with httpx.AsyncClient(trust_env=False) as client:
            for i in range(max_retries):
                try:
                    await asyncio.sleep(interval)
                    resp = await client.get(
                        f"{self.BASE_URL}/api/v1/coding/jobs/{job_id}",
                        timeout=6
                    )
                    
                    if resp.status_code in (200, 422):
                        data = resp.json()
                        # 422 也是一种成功状态（需要人工确认），包含结果数据
                        if "data" in data:
                            return data["data"]
                    
                    # 如果还是 processing，循环继续
                    # 如果不是 success/accepted，打印日志
                    if resp.status_code not in (200, 202, 422):
                        logger.warning(f"Polling job {job_id} status: {resp.status_code}")
                        
                except Exception as e:
                    logger.warning(f"Error polling job {job_id}: {e}")
            
            raise TimeoutError("Coding job polling timed out")

# 单例
external_coding_service = ExternalCodingService()

def get_external_coding_service() -> ExternalCodingService:
    return external_coding_service
