"""
外部 ICD 编码服务封装
对接 http://122.51.111.253:8002 的异步编码服务
"""

import asyncio
import uuid
from typing import Dict, Any, Optional

import httpx
try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


class ExternalCodingService:
    """外部 ICD 编码服务"""
    
    BASE_URL = "http://122.51.111.253:8002"
    MAX_RETRIES = 15
    POLL_INTERVAL = 2  # 秒
    
    async def extract_coding(
        self,
        medical_text: str,
        patient_context: Optional[Dict[str, Any]] = None,
        document_type: str = "admission_note"
    ) -> Dict[str, Any]:
        """
        从病历文本中提取 ICD 编码
        
        Args:
            medical_text: 病历文本
            patient_context: 患者上下文 {"gender": "M/F", "age": 58}
            document_type: 文书类型 (admission_note, discharge_note, etc.)
            
        Returns:
            包含 coding_data 的结果字典
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        try:
            # 1. 提交编码任务
            job_id = await self._submit_job(
                request_id=request_id,
                text_content=medical_text,
                document_type=document_type,
                patient_context=patient_context or {"gender": "M", "age": 50}
            )
            
            if not job_id:
                logger.error("提交编码任务失败，未获得 job_id")
                return {"success": False, "error": "提交任务失败"}
            
            logger.info(f"编码任务已提交: job_id={job_id}")
            
            # 2. 轮询结果
            result = await self._poll_result(job_id)
            
            return result
            
        except Exception as e:
            logger.error(f"外部编码服务调用失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _submit_job(
        self,
        request_id: str,
        text_content: str,
        document_type: str,
        patient_context: Dict[str, Any]
    ) -> Optional[str]:
        """提交编码任务，返回 job_id"""
        url = f"{self.BASE_URL}/api/v1/coding/extract"
        
        payload = {
            "request_id": request_id,
            "document_type": document_type,
            "text_content": text_content,
            "patient_context": patient_context,
            "coding_mode": "default"
        }
        
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            resp = await client.post(url, json=payload)
            
            if resp.status_code == 202:
                data = resp.json()
                return data.get("data", {}).get("job_id")
            else:
                logger.error(f"提交任务失败: status={resp.status_code}, body={resp.text}")
                return None
    
    async def _poll_result(self, job_id: str) -> Dict[str, Any]:
        """轮询编码结果"""
        url = f"{self.BASE_URL}/api/v1/coding/jobs/{job_id}"
        
        for i in range(self.MAX_RETRIES):
            await asyncio.sleep(self.POLL_INTERVAL)
            
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
                    resp = await client.get(url)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        coding_data = data.get("data", {}).get("coding_data")
                        if coding_data:
                            logger.info(f"编码完成: job_id={job_id}, retry={i+1}")
                            return {
                                "success": True,
                                "needs_review": False,
                                "data": data.get("data", {}),
                                "warnings": data.get("data", {}).get("warnings", [])
                            }
                    
                    elif resp.status_code == 422:
                        # 成功但需人工确认
                        data = resp.json()
                        logger.warn(f"编码完成但需人工确认: job_id={job_id}")
                        return {
                            "success": True,
                            "needs_review": True,
                            "data": data.get("data", {}),
                            "warnings": data.get("data", {}).get("warnings", [])
                        }
                    
                    elif resp.status_code == 500:
                        logger.error(f"编码服务内部错误: job_id={job_id}")
                        return {"success": False, "error": "编码服务内部错误"}
                    
                    # 其他状态码，继续轮询
                    logger.debug(f"轮询中: job_id={job_id}, retry={i+1}, status={resp.status_code}")
                    
            except Exception as e:
                logger.error(f"轮询请求失败: {str(e)}")
        
        # 超时
        logger.error(f"编码任务超时: job_id={job_id}")
        return {"success": False, "error": "编码提取超时，请稍后重试"}


# 全局服务实例
external_coding_service = ExternalCodingService()
