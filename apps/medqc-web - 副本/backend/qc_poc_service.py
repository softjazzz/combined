#!/usr/bin/env python3
"""
质控概念验证服务（PoC）

用途：
- 用于验证语义规则引擎与现有系统的集成可行性；
- 主要配合 `_archived_entry_points/main_api.py` 使用，不再作为正式质控实现的一部分。

注意：
- 当前项目的正式质控服务位于 `app/services/qc_service.py` 和 `app/services/sichuan_qc_service.py`；
- 新功能开发应优先基于 `app/` 下的模块化服务，本文件仅保留为历史参考和实验用例。
"""

import json
import logging
import sys
import os
import httpx
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib

# 添加语义规则引擎路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'semantic_rules_engine'))

from semantic_rule_engine import SemanticRuleEngine, SemanticRuleResult

logger = logging.getLogger(__name__)

# 真实LLM客户端类
class RealLLMClient:
    """真实LLM客户端，调用实际的LLM API"""

    def __init__(self, api_endpoint: str = None, api_key: str = None, model: str = None):
        # 如果没有提供参数，从数据库加载质控配置
        if not all([api_endpoint, api_key, model]):
            config = self._load_qc_config_from_db()
            if config:
                self.api_endpoint = api_endpoint or config.get('base_endpoint', '')
                self.api_key = api_key or config.get('api_key_encrypted', '')
                self.model = model or config.get('model_code', 'qwen2.5-14b-instruct')
            else:
                # 回退到默认配置（仅用于本地 PoC 调试，不应在生产环境中依赖）
                self.api_endpoint = api_endpoint or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
                # 不再在代码中硬编码真实密钥，改为占位符，实际使用时需通过环境变量或数据库配置提供
                self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY', '')
                self.model = model or 'qwen2.5-14b-instruct'
        else:
            self.api_endpoint = api_endpoint
            self.api_key = api_key
            self.model = model

        self.model_name = f"real-llm-{self.model}"
        logger.info(f"初始化真实LLM客户端: {self.model} @ {self.api_endpoint}")

    def _load_qc_config_from_db(self):
        """从数据库加载质控配置"""
        try:
            from supabase import create_client
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')

            if not supabase_url or not supabase_key:
                logger.warning("Supabase配置不完整，无法从数据库加载LLM配置")
                return None

            supabase = create_client(supabase_url, supabase_key)

            # 查询质控分析配置（包含API密钥）
            result = supabase.table('user_llm_configs').select(
                '''
                *,
                llm_api_providers!inner(provider_code, provider_name, base_endpoint),
                llm_models!inner(model_code, model_name, parameters)
                '''
            ).eq('config_name', 'qc_analysis').eq('is_active', True).limit(1).execute()

            if result.data:
                config_data = result.data[0]
                provider = config_data['llm_api_providers']
                model = config_data['llm_models']

                # 构建完整配置
                full_config = {
                    'provider_code': provider['provider_code'],
                    'provider_name': provider['provider_name'],
                    'base_endpoint': provider['base_endpoint'],
                    'model_code': model['model_code'],
                    'model_name': model['model_name'],
                    'api_key_encrypted': config_data.get('api_key_encrypted', ''),
                    'custom_endpoint': config_data.get('custom_endpoint'),
                    'custom_parameters': config_data.get('custom_parameters', {})
                }

                logger.info("从数据库加载质控LLM配置成功")
                return full_config
            else:
                logger.warning("数据库中未找到质控LLM配置")
                return None

        except Exception as e:
            logger.error(f"从数据库加载LLM配置失败: {e}")
            return None

    def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
        """执行语义规则（同步方法，符合语义规则引擎期望的接口）"""
        logger.info(f"真实LLM调用，规则ID: {rule_id}，上下文长度: {len(context)}")

        # 如果没有配置API密钥，回退到Mock模式
        if not self.api_key:
            logger.warning("未配置LLM API密钥，回退到Mock模式")
            mock_client = MockLLMClient()
            return mock_client.execute_semantic_rule(rule_id, context)

        try:
            # 检查是否已经在事件循环中
            try:
                current_loop = asyncio.get_running_loop()
                # 如果已经在事件循环中，使用同步方式调用
                logger.info("检测到运行中的事件循环，使用同步LLM调用")
                result = self._call_llm_sync(rule_id, context)
                return result
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._call_llm_async(rule_id, context))
                    return result
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"真实LLM调用失败，回退到Mock模式: {e}")
            mock_client = MockLLMClient()
            return mock_client.execute_semantic_rule(rule_id, context)

    def _call_llm_sync(self, rule_id: str, context: str) -> Dict[str, Any]:
        """同步调用LLM API（用于避免事件循环冲突）"""

        # 构建质控分析的提示词
        prompt = self._build_qc_prompt(rule_id, context)

        # 构建API请求
        request_body = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的医疗质控专家，请严格按照JSON格式输出分析结果。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 1000
        }

        # 直接调用外部LLM API（避免循环调用）
        import requests
        try:
            response = requests.post(
                self.api_endpoint + '/chat/completions',
                json=request_body,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                },
                timeout=30
            )

            if not response.ok:
                raise Exception(f"LLM API调用失败: {response.status_code} {response.text}")

            llm_response = response.json()

            # 解析LLM响应并转换为期望的格式
            return self._parse_llm_response(llm_response, rule_id)

        except Exception as e:
            logger.error(f"同步LLM调用失败: {e}")
            raise e

    async def _call_llm_async(self, rule_id: str, context: str) -> Dict[str, Any]:
        """异步调用LLM API"""

        # 构建质控分析的提示词
        prompt = self._build_qc_prompt(rule_id, context)

        # 构建API请求
        request_body = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的医疗质控专家，请严格按照JSON格式输出分析结果。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 1000
        }

        # 通过后端代理调用LLM API
        proxy_payload = {
            'requestBody': request_body,
            'apiConfig': {
                'apiEndpoint': self.api_endpoint,
                'apiKey': self.api_key
            }
        }

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                'http://localhost:8001/api/llm/parse-text',
                json=proxy_payload,
                headers={'Content-Type': 'application/json'}
            )

            if not response.is_success:
                raise Exception(f"LLM API调用失败: {response.status_code} {response.text}")

            llm_response = response.json()

            # 解析LLM响应并转换为期望的格式
            return self._parse_llm_response(llm_response, rule_id)

    def _build_qc_prompt(self, rule_id: str, context: str) -> str:
        """构建质控分析的提示词"""

        rule_prompts = {
            'POC_001': '''
你是一个专业的医疗质控专家。请分析以下医疗文档是否包含主诉内容。

分析要求：
1. 检查文档中是否包含患者的主诉信息
2. 主诉可能以多种形式出现：
   - "主诉："开头的标准格式
   - "以...为主诉"的描述格式
   - "因...就诊"的就诊原因描述
   - 其他表达患者主要症状或就诊原因的内容

文档内容：
{context}

请以JSON格式回复：
{{
  "compliant": true/false,
  "confidence": 0.0-1.0,
  "evidence": "具体的证据文本或缺失说明",
  "reasoning": "分析推理过程"
}}
''',
            'POC_002': '''
你是一个专业的医疗质控专家。请分析以下医疗文档是否包含现病史内容。

分析要求：
1. 检查文档中是否包含患者的现病史信息
2. 现病史可能以多种形式出现：
   - "现病史："开头的标准格式
   - "本病例特点："的描述
   - "病史摘要"或"病史特点"
   - 对患者当前疾病发展过程的详细描述

文档内容：
{context}

请以JSON格式回复：
{{
  "compliant": true/false,
  "confidence": 0.0-1.0,
  "evidence": "具体的证据文本或缺失说明",
  "reasoning": "分析推理过程"
}}
'''
        }

        template = rule_prompts.get(rule_id, '''
你是一个专业的医疗质控专家。请分析以下医疗文档的质量。

文档内容：
{context}

请以JSON格式回复：
{{
  "compliant": true/false,
  "confidence": 0.0-1.0,
  "evidence": "分析证据",
  "reasoning": "分析推理"
}}
''')

        return template.format(context=context)

    def _parse_llm_response(self, response: Dict[str, Any], rule_id: str) -> Dict[str, Any]:
        """解析LLM响应并转换为期望的格式"""

        try:
            # 提取响应内容
            content = ''
            if 'choices' in response and response['choices']:
                content = response['choices'][0].get('message', {}).get('content', '')
            elif 'output' in response:
                # 阿里云DashScope格式
                content = response['output'].get('text', '')

            if not content:
                raise Exception("LLM响应为空")

            # 尝试解析JSON
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                # 如果不是标准JSON，尝试提取关键信息
                result_json = self._extract_info_from_text(content)

            # 转换为期望的格式（与MockLLMClient保持一致）
            return {
                "content": json.dumps({
                    "compliant": result_json.get('compliant', False),
                    "confidence": float(result_json.get('confidence', 0.0)),
                    "evidence": result_json.get('evidence', '无法提取证据'),
                    "reasoning": result_json.get('reasoning', '无法提取推理过程')
                }, ensure_ascii=False),
                "token_usage": response.get('usage', {"prompt": 100, "completion": 50, "total": 150})
            }

        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return {
                "content": json.dumps({
                    "compliant": False,
                    "confidence": 0.0,
                    "evidence": f'响应解析失败: {str(e)}',
                    "reasoning": '系统错误'
                }, ensure_ascii=False),
                "token_usage": {"prompt": 100, "completion": 50, "total": 150}
            }

    def _extract_info_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取关键信息（当JSON解析失败时的备用方案）"""

        text_lower = text.lower()

        # 判断是否合规
        compliant = any(keyword in text_lower for keyword in [
            '符合', '通过', '满足', '包含', '存在', 'true', 'compliant'
        ])

        return {
            'compliant': compliant,
            'confidence': 0.5,
            'evidence': text[:200] + '...' if len(text) > 200 else text,
            'reasoning': '基于关键词匹配的简化分析'
        }

class MockLLMClient:
    """模拟LLM客户端，用于概念验证"""

    def __init__(self):
        self.model_name = "mock-llm-v1.0"

    def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
        """执行语义规则（同步方法，符合语义规则引擎期望的接口）"""
        logger.info(f"模拟LLM调用，规则ID: {rule_id}，上下文长度: {len(context)}")

        # 简单的规则匹配逻辑，用于概念验证
        if rule_id == "POC_001":  # 缺少主诉
            if "主诉：" in context or "主诉:" in context:
                return {
                    "content": json.dumps({
                        "compliant": True,
                        "confidence": 0.95,
                        "evidence": "文档中包含'主诉：'字段",
                        "reasoning": "检测到标准的主诉格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 100, "completion": 50, "total": 150}
                }
            else:
                return {
                    "content": json.dumps({
                        "compliant": False,
                        "confidence": 0.90,
                        "evidence": "文档中未找到'主诉：'字段",
                        "reasoning": "缺少标准的主诉格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 100, "completion": 50, "total": 150}
                }

        elif rule_id == "POC_002":  # 缺少现病史
            if "现病史：" in context or "现病史:" in context:
                return {
                    "content": json.dumps({
                        "compliant": True,
                        "confidence": 0.92,
                        "evidence": "文档中包含'现病史：'字段",
                        "reasoning": "检测到标准的现病史格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 120, "completion": 60, "total": 180}
                }
            else:
                return {
                    "content": json.dumps({
                        "compliant": False,
                        "confidence": 0.88,
                        "evidence": "文档中未找到'现病史：'字段",
                        "reasoning": "缺少标准的现病史格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 120, "completion": 60, "total": 180}
                }

        # 默认返回
        return {
            "content": json.dumps({
                "compliant": True,
                "confidence": 0.5,
                "evidence": "无法确定",
                "reasoning": "模拟响应"
            }, ensure_ascii=False),
            "token_usage": {"prompt": 50, "completion": 30, "total": 80}
        }

    async def generate_response(self, context: str, **kwargs) -> Dict[str, Any]:
        """模拟LLM响应，用于概念验证"""
        logger.info(f"模拟LLM调用，上下文长度: {len(context)}")
        
        # 简单的规则匹配逻辑，用于概念验证
        if "主诉" in context:
            if "主诉：" in context or "主诉:" in context:
                return {
                    "content": json.dumps({
                        "compliant": True,
                        "confidence": 0.95,
                        "evidence": "文档中包含'主诉：'字段",
                        "reasoning": "检测到标准的主诉格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 100, "completion": 50, "total": 150}
                }
            else:
                return {
                    "content": json.dumps({
                        "compliant": False,
                        "confidence": 0.90,
                        "evidence": "文档中未找到'主诉：'字段",
                        "reasoning": "缺少标准的主诉格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 100, "completion": 50, "total": 150}
                }
        
        elif "现病史" in context:
            if "现病史：" in context or "现病史:" in context:
                return {
                    "content": json.dumps({
                        "compliant": True,
                        "confidence": 0.92,
                        "evidence": "文档中包含'现病史：'字段",
                        "reasoning": "检测到标准的现病史格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 120, "completion": 60, "total": 180}
                }
            else:
                return {
                    "content": json.dumps({
                        "compliant": False,
                        "confidence": 0.88,
                        "evidence": "文档中未找到'现病史：'字段",
                        "reasoning": "缺少标准的现病史格式"
                    }, ensure_ascii=False),
                    "token_usage": {"prompt": 120, "completion": 60, "total": 180}
                }
        
        # 默认返回
        return {
            "content": json.dumps({
                "compliant": True,
                "confidence": 0.5,
                "evidence": "无法确定",
                "reasoning": "模拟响应"
            }, ensure_ascii=False),
            "token_usage": {"prompt": 50, "completion": 30, "total": 80}
        }

class QCPOCService:
    """质控概念验证服务"""

    def __init__(self, use_real_llm: bool = None):
        """
        初始化服务

        Args:
            use_real_llm: 是否使用真实LLM。如果为None，则根据环境变量决定
        """
        # 决定使用哪种LLM客户端
        if use_real_llm is None:
            # 根据环境变量决定
            use_real_llm = os.getenv('USE_REAL_LLM', 'false').lower() in ('true', '1', 'yes')

        if use_real_llm:
            logger.info("使用真实LLM客户端")
            self.llm_client = RealLLMClient()
        else:
            logger.info("使用Mock LLM客户端")
            self.llm_client = MockLLMClient()

        self.use_real_llm = use_real_llm
        self.qc_engine = SemanticRuleEngine(
            llm_client=self.llm_client,
            config={"timeout": 30, "max_retries": 2}
        )
        logger.info("质控概念验证服务初始化完成")
    
    def calculate_content_hash(self, content: str) -> str:
        """计算内容哈希，用于幂等性检查"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def analyze_document(self, document_id: str, content: str, rule_ids: List[str] = None) -> Dict[str, Any]:
        """
        分析单个文档
        
        Args:
            document_id: 文档ID
            content: 文档内容
            rule_ids: 要执行的规则ID列表，默认执行所有概念验证规则
            
        Returns:
            分析结果字典
        """
        try:
            logger.info(f"开始分析文档 {document_id}，内容长度: {len(content)}")
            
            # 如果未指定规则，使用概念验证规则
            if not rule_ids:
                rule_ids = ["POC_001", "POC_002"]  # 缺少主诉、缺少现病史
            
            # 执行规则分析
            results = []
            total_score = 100
            failed_rules = 0
            
            for rule_id in rule_ids:
                try:
                    result = self.qc_engine.execute_rule(rule_id, {"content": content})
                    results.append({
                        "rule_id": result.rule_id,
                        "rule_name": result.rule_name,
                        "compliant": result.compliant,
                        "confidence": result.confidence,
                        "evidence": result.evidence,
                        "reasoning": result.reasoning,
                        "execution_time": result.execution_time
                    })
                    
                    # 计算扣分
                    if not result.compliant:
                        failed_rules += 1
                        # 简单扣分策略：每个失败规则扣5分
                        total_score -= 5
                        
                except Exception as e:
                    logger.error(f"执行规则 {rule_id} 失败: {e}")
                    results.append({
                        "rule_id": rule_id,
                        "rule_name": f"规则{rule_id}",
                        "compliant": False,
                        "confidence": 0.0,
                        "evidence": f"执行失败: {str(e)}",
                        "reasoning": "规则执行异常",
                        "execution_time": 0.0
                    })
                    failed_rules += 1
                    total_score -= 5
            
            # 确定总体状态
            if failed_rules == 0:
                qc_status = "passed"
            elif failed_rules <= len(rule_ids) // 2:
                qc_status = "warning"
            else:
                qc_status = "failed"
            
            # 计算内容哈希
            content_hash = self.calculate_content_hash(content)
            
            analysis_result = {
                "document_id": document_id,
                "qc_status": qc_status,
                "qc_score": max(0, total_score),  # 确保分数不为负
                "content_hash": content_hash,
                "applied_rules": len(rule_ids),
                "failed_rules": failed_rules,
                "results": results,
                "analysis_time": datetime.utcnow().isoformat() + "Z",
                "analysis_version": "poc_v1.0"
            }
            
            logger.info(f"文档 {document_id} 分析完成，状态: {qc_status}，分数: {total_score}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"分析文档 {document_id} 时发生错误: {e}")
            raise Exception(f"质控分析失败: {str(e)}")
    
    def get_available_rules(self) -> List[Dict[str, Any]]:
        """获取可用的质控规则列表"""
        rules = []
        for rule_id, rule_def in self.qc_engine.rules.items():
            rules.append({
                "rule_id": rule_id,
                "rule_name": rule_def.rule_name,
                "description": rule_def.description,
                "category": rule_def.category,
                "complexity": rule_def.complexity.value,
                "is_active": True
            })
        return rules
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return {
            "total_rules": len(self.qc_engine.rules),
            "execution_stats": self.qc_engine.execution_stats,
            "engine_version": "poc_v1.0"
        }

# 全局服务实例
qc_poc_service = None

def get_qc_poc_service(use_real_llm: bool = None) -> QCPOCService:
    """
    获取质控概念验证服务实例

    Args:
        use_real_llm: 是否使用真实LLM。如果为None，则根据环境变量决定
    """
    global qc_poc_service
    if qc_poc_service is None:
        qc_poc_service = QCPOCService(use_real_llm=use_real_llm)
    return qc_poc_service

def reset_qc_poc_service():
    """重置质控服务实例（用于切换LLM类型）"""
    global qc_poc_service
    qc_poc_service = None
