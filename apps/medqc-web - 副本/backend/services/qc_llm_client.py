"""
质控专用LLM客户端适配器
复用现有的LLM API组件，为质控分析提供专门的接口
"""

import json
import time
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from supabase import create_client, Client
import os
from datetime import datetime

@dataclass
class QCLLMConfig:
    """质控LLM配置"""
    provider_code: str
    model_code: str
    api_endpoint: str
    api_key: str
    custom_parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_parameters is None:
            self.custom_parameters = {}

@dataclass
class QCAnalysisResult:
    """质控分析结果"""
    compliant: bool
    confidence: float
    evidence: str
    reasoning: str
    execution_time: float
    error: Optional[str] = None

class QCLLMClient:
    """质控专用LLM客户端"""
    
    def __init__(self, config: Optional[QCLLMConfig] = None):
        self.config = config
        self.supabase: Optional[Client] = None
        self._init_supabase()
        
        # 如果没有提供配置，尝试从数据库加载默认质控配置
        if not self.config:
            self._load_default_qc_config()
    
    def _init_supabase(self):
        """初始化Supabase客户端"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            
            if supabase_url and supabase_key:
                self.supabase = create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"[QC LLM Client] Supabase初始化失败: {e}")
    
    def _load_default_qc_config(self):
        """从数据库加载默认质控配置"""
        if not self.supabase:
            print("[QC LLM Client] 无法连接数据库，使用Mock配置")
            self._use_mock_config()
            return
        
        try:
            # 查询质控分析专用的LLM配置
            result = self.supabase.table('user_llm_configs').select(
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
                
                self.config = QCLLMConfig(
                    provider_code=provider['provider_code'],
                    model_code=model['model_code'],
                    api_endpoint=config_data.get('custom_endpoint') or provider['base_endpoint'],
                    api_key=config_data.get('api_key_encrypted', ''),  # 实际使用时需要解密
                    custom_parameters={
                        **model.get('parameters', {}),
                        **config_data.get('custom_parameters', {})
                    }
                )
                print(f"[QC LLM Client] 加载质控配置: {provider['provider_name']} - {model['model_name']}")
            else:
                print("[QC LLM Client] 未找到质控配置，使用默认配置")
                self._load_default_config()
                
        except Exception as e:
            print(f"[QC LLM Client] 加载配置失败: {e}")
            self._use_mock_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        if not self.supabase:
            self._use_mock_config()
            return
            
        try:
            # 查询默认配置
            result = self.supabase.table('user_llm_configs').select(
                '''
                *,
                llm_api_providers!inner(provider_code, provider_name, base_endpoint),
                llm_models!inner(model_code, model_name, parameters)
                '''
            ).eq('config_name', 'default').eq('is_active', True).limit(1).execute()
            
            if result.data:
                config_data = result.data[0]
                provider = config_data['llm_api_providers']
                model = config_data['llm_models']
                
                self.config = QCLLMConfig(
                    provider_code=provider['provider_code'],
                    model_code=model['model_code'],
                    api_endpoint=config_data.get('custom_endpoint') or provider['base_endpoint'],
                    api_key=config_data.get('api_key_encrypted', ''),
                    custom_parameters=model.get('parameters', {})
                )
                print(f"[QC LLM Client] 使用默认配置: {provider['provider_name']} - {model['model_name']}")
            else:
                self._use_mock_config()
                
        except Exception as e:
            print(f"[QC LLM Client] 加载默认配置失败: {e}")
            self._use_mock_config()
    
    def _use_mock_config(self):
        """使用Mock配置"""
        self.config = QCLLMConfig(
            provider_code='mock',
            model_code='mock',
            api_endpoint='http://localhost:8001/mock',
            api_key='mock-key'
        )
        print("[QC LLM Client] 使用Mock配置")
    
    async def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
        """
        执行语义规则分析
        保持与MockLLMClient相同的接口
        """
        start_time = time.time()
        
        try:
            # 如果是Mock配置，使用Mock逻辑
            if self.config.provider_code == 'mock':
                return await self._execute_mock_rule(rule_id, context)
            
            # 构建质控分析的提示词
            prompt = self._build_qc_prompt(rule_id, context)
            
            # 调用真实LLM API
            result = await self._call_llm_api(prompt)
            
            # 解析LLM响应
            analysis_result = self._parse_llm_response(result, rule_id)
            
            execution_time = time.time() - start_time
            analysis_result.execution_time = execution_time
            
            return {
                'compliant': analysis_result.compliant,
                'confidence': analysis_result.confidence,
                'evidence': analysis_result.evidence,
                'reasoning': analysis_result.reasoning,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"[QC LLM Client] 规则执行失败 {rule_id}: {e}")
            
            return {
                'compliant': False,
                'confidence': 0.0,
                'evidence': f'分析失败: {str(e)}',
                'reasoning': '系统错误',
                'execution_time': execution_time
            }
    
    def _build_qc_prompt(self, rule_id: str, context: str) -> str:
        """构建质控分析的提示词"""
        
        # 根据规则ID构建专门的提示词
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
    
    async def _call_llm_api(self, prompt: str) -> Dict[str, Any]:
        """调用LLM API"""
        
        # 构建API请求
        request_body = self._build_api_request(prompt)
        
        # 通过后端代理调用（复用现有的代理逻辑）
        proxy_payload = {
            'requestBody': request_body,
            'apiConfig': {
                'apiEndpoint': self.config.api_endpoint,
                'apiKey': self.config.api_key
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
            
            return response.json()
    
    def _build_api_request(self, prompt: str) -> Dict[str, Any]:
        """构建API请求体"""
        
        # 基础OpenAI兼容格式
        request_body = {
            'model': self.config.model_code,
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
        
        # 合并自定义参数
        request_body.update(self.config.custom_parameters)
        
        return request_body
    
    def _parse_llm_response(self, response: Dict[str, Any], rule_id: str) -> QCAnalysisResult:
        """解析LLM响应"""
        
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
            
            return QCAnalysisResult(
                compliant=result_json.get('compliant', False),
                confidence=float(result_json.get('confidence', 0.0)),
                evidence=result_json.get('evidence', '无法提取证据'),
                reasoning=result_json.get('reasoning', '无法提取推理过程'),
                execution_time=0.0  # 将在调用方设置
            )
            
        except Exception as e:
            return QCAnalysisResult(
                compliant=False,
                confidence=0.0,
                evidence=f'响应解析失败: {str(e)}',
                reasoning='系统错误',
                execution_time=0.0,
                error=str(e)
            )
    
    def _extract_info_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取关键信息（当JSON解析失败时的备用方案）"""
        
        # 简单的关键词匹配逻辑
        text_lower = text.lower()
        
        # 判断是否合规
        compliant = any(keyword in text_lower for keyword in [
            '符合', '通过', '满足', '包含', '存在', 'true', 'compliant'
        ])
        
        # 提取置信度
        confidence = 0.5  # 默认置信度
        
        return {
            'compliant': compliant,
            'confidence': confidence,
            'evidence': text[:200] + '...' if len(text) > 200 else text,
            'reasoning': '基于关键词匹配的简化分析'
        }
    
    async def _execute_mock_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
        """执行Mock规则（保持与原有逻辑一致）"""
        
        # 模拟处理时间
        await asyncio.sleep(0.0001)
        
        # Mock逻辑
        mock_results = {
            'POC_001': {
                'compliant': '主诉：' in context or '为主诉' in context,
                'confidence': 0.90,
                'evidence': '文档中未找到\'主诉：\'字段' if '主诉：' not in context and '为主诉' not in context else '找到主诉内容',
                'reasoning': '缺少标准的主诉格式' if '主诉：' not in context and '为主诉' not in context else '包含主诉信息'
            },
            'POC_002': {
                'compliant': '现病史：' in context or '本病例特点：' in context,
                'confidence': 0.88,
                'evidence': '文档中未找到\'现病史：\'字段' if '现病史：' not in context and '本病例特点：' not in context else '找到现病史内容',
                'reasoning': '缺少标准的现病史格式' if '现病史：' not in context and '本病例特点：' not in context else '包含现病史信息'
            }
        }
        
        result = mock_results.get(rule_id, {
            'compliant': True,
            'confidence': 0.5,
            'evidence': 'Mock分析结果',
            'reasoning': 'Mock推理过程'
        })
        
        result['execution_time'] = 0.0001
        return result

# 导入asyncio（在文件顶部添加）
import asyncio
