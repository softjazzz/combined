"""
审计日志模块
记录规则执行和命中情况
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import asdict

from .evaluator import EvaluationResult, RuleHit
from .dsl import TriggerEvent


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, supabase_client=None, fallback_to_file: bool = True):
        self.supabase = supabase_client
        self.fallback_to_file = fallback_to_file
        
        # 设置文件日志
        self.logger = logging.getLogger('qc_engine_audit')
        self.logger.setLevel(logging.INFO)
        
        # 如果没有处理器，添加一个
        if not self.logger.handlers:
            handler = logging.FileHandler('qc_engine_audit.log')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_evaluation(
        self,
        event_type: Optional[TriggerEvent],
        context: Dict[str, Any],
        result: EvaluationResult,
        visit_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        记录评估结果
        
        Args:
            event_type: 触发事件类型
            context: 评估上下文
            result: 评估结果
            visit_id: 就诊 ID
            user_id: 用户 ID
        
        Returns:
            是否成功记录
        """
        try:
            # 准备审计数据
            audit_data = self._prepare_audit_data(
                event_type, context, result, visit_id, user_id
            )
            
            # 尝试写入数据库
            if self.supabase:
                success = self._log_to_database(audit_data)
                if success:
                    return True
            
            # 回退到文件日志
            if self.fallback_to_file:
                self._log_to_file(audit_data)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to log evaluation: {e}")
            return False
    
    def log_batch_evaluation(
        self,
        event_type: Optional[TriggerEvent],
        contexts: List[Dict[str, Any]],
        results: List[EvaluationResult],
        user_id: Optional[str] = None
    ) -> int:
        """
        批量记录评估结果
        
        Returns:
            成功记录的数量
        """
        success_count = 0
        
        for context, result in zip(contexts, results):
            # 尝试从 context 中提取 visit_id
            visit_id = context.get('visit', {}).get('id')
            
            if self.log_evaluation(event_type, context, result, visit_id, user_id):
                success_count += 1
        
        return success_count
    
    def _prepare_audit_data(
        self,
        event_type: Optional[TriggerEvent],
        context: Dict[str, Any],
        result: EvaluationResult,
        visit_id: Optional[str],
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """准备审计数据"""
        # 对敏感信息进行脱敏
        safe_context = self._sanitize_context(context)
        
        # 构建审计记录
        audit_data = {
            'event_type': (event_type.value if hasattr(event_type, 'value') else str(event_type)) if event_type else None,
            'visit_id': visit_id,
            'user_id': user_id,
            'decision': getattr(result.decision, 'value', str(result.decision)),
            'execution_time_ms': result.execution_time_ms,
            'total_hits': len(result.hits),
            'context_json': safe_context,
            'metadata': result.metadata,
            'created_at': datetime.now().isoformat(),
            'hits': []
        }
        
        # 添加命中详情
        for hit in result.hits:
            hit_data = {
                'rule_id': hit.rule_id,
                'rule_code': hit.rule_code,
                'rule_name': hit.rule_name,
                'severity': getattr(hit.severity, 'value', str(hit.severity)),
                'messages': hit.messages,
                'execution_time_ms': hit.execution_time_ms
            }
            audit_data['hits'].append(hit_data)
        
        return audit_data
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        对上下文进行脱敏处理
        
        Args:
            context: 原始上下文
        
        Returns:
            脱敏后的上下文
        """
        # 复制上下文
        safe_context = json.loads(json.dumps(context))
        
        # 定义需要脱敏的字段
        sensitive_fields = [
            'id_card', 'id_number', 'ssn',
            'phone', 'mobile', 'tel',
            'email', 'address'
        ]
        
        def mask_value(value: str) -> str:
            """对值进行掩码处理"""
            if len(value) <= 4:
                return '****'
            return value[:2] + '*' * (len(value) - 4) + value[-2:]
        
        def sanitize_dict(d: Dict) -> Dict:
            """递归脱敏字典"""
            for key, value in d.items():
                if key.lower() in sensitive_fields and isinstance(value, str):
                    d[key] = mask_value(value)
                elif isinstance(value, dict):
                    d[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    d[key] = [
                        sanitize_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
            return d
        
        return sanitize_dict(safe_context)
    
    def _log_to_database(self, audit_data: Dict[str, Any]) -> bool:
        """
        将审计数据写入数据库
        
        Args:
            audit_data: 审计数据
        
        Returns:
            是否成功
        """
        if not self.supabase:
            return False
        
        try:
            # 分离命中记录
            hits = audit_data.pop('hits', [])
            
            # 插入主记录
            response = self.supabase.table('yibao_violations').insert({
                'event_type': audit_data['event_type'],
                'visit_id': audit_data['visit_id'],
                'user_id': audit_data['user_id'],
                'decision': audit_data['decision'],
                'execution_time_ms': int(audit_data['execution_time_ms']),
                'total_hits': audit_data['total_hits'],
                'context_json': audit_data['context_json'],
                'metadata': audit_data['metadata']
            }).execute()
            
            if not response.data:
                return False
            
            violation_id = response.data[0]['id']
            
            # 插入命中详情
            for hit in hits:
                self.supabase.table('yibao_violation_hits').insert({
                    'violation_id': violation_id,
                    'rule_id': hit['rule_id'],
                    'rule_code': hit['rule_code'],
                    'rule_name': hit['rule_name'],
                    'severity': hit['severity'],
                    'messages': hit['messages'],
                    'execution_time_ms': hit['execution_time_ms']
                }).execute()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Database write failed: {e}")
            return False
    
    def _log_to_file(self, audit_data: Dict[str, Any]) -> None:
        """
        将审计数据写入文件日志
        
        Args:
            audit_data: 审计数据
        """
        # 转换为 JSON 字符串
        log_message = json.dumps(audit_data, ensure_ascii=False)
        
        # 根据决策级别记录
        if audit_data['decision'] == 'block':
            self.logger.warning(f"BLOCK: {log_message}")
        elif audit_data['decision'] == 'warn':
            self.logger.info(f"WARN: {log_message}")
        else:
            self.logger.info(f"PASS: {log_message}")
    
    def query_violations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        visit_id: Optional[str] = None,
        rule_code: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        查询违规记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            visit_id: 就诊 ID
            rule_code: 规则代码
            decision: 决策类型
            limit: 返回记录数限制
        
        Returns:
            违规记录列表
        """
        if not self.supabase:
            return []
        
        try:
            query = self.supabase.table('yibao_violations').select('*')
            
            if start_date:
                query = query.gte('created_at', start_date.isoformat())
            if end_date:
                query = query.lte('created_at', end_date.isoformat())
            if visit_id:
                query = query.eq('visit_id', visit_id)
            if decision:
                query = query.eq('decision', decision)
            
            query = query.limit(limit)
            response = query.execute()
            
            return response.data or []
            
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            return []


# 创建全局审计日志实例
audit_logger = AuditLogger()


# 导出
__all__ = [
    'AuditLogger',
    'audit_logger'
]
