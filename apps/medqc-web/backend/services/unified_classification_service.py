#!/usr/bin/env python3
"""
统一医疗文书分类服务
支持多版本算法动态切换和性能监控
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .classification_config import classification_config, ClassificationVersion
from .advanced_classification_engine import AdvancedClassificationEngine

logger = logging.getLogger(__name__)

class UnifiedClassificationService:
    """统一分类服务"""
    
    def __init__(self):
        """初始化分类服务"""
        self.config = classification_config
        self.advanced_engine = AdvancedClassificationEngine()
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_processing_time": 0.0,
            "version_usage": {}
        }
    
    async def classify_medical_text(self, 
                                  raw_text: str, 
                                  options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        统一的医疗文书分类接口
        
        Args:
            raw_text: 原始医疗文本
            options: 分类选项
            
        Returns:
            分类结果
        """
        start_time = time.time()
        self.performance_stats["total_requests"] += 1
        
        try:
            # 获取当前版本和配置
            current_version = self.config.get_current_version()
            algorithm_settings = self.config.get_algorithm_settings(current_version)
            
            # 合并选项
            merged_options = algorithm_settings.copy()
            if options:
                merged_options.update(options)
            
            # 记录版本使用情况
            version_key = current_version.value
            self.performance_stats["version_usage"][version_key] = \
                self.performance_stats["version_usage"].get(version_key, 0) + 1
            
            # 执行分类
            result = await self._execute_classification(raw_text, current_version, merged_options)
            
            # 检查结果质量
            if not self._validate_result(result):
                logger.warning(f"分类结果质量不佳，尝试回退版本")
                fallback_version = self.config.get_fallback_version()
                if fallback_version != current_version:
                    result = await self._execute_classification(raw_text, fallback_version, merged_options)
                    result["fallback_used"] = True
                    result["fallback_version"] = fallback_version.value
            
            # 添加元数据
            processing_time = time.time() - start_time
            result.update({
                "algorithm_version": current_version.value,
                "processing_time": round(processing_time, 3),
                "timestamp": datetime.now().isoformat(),
                "config_version": self.config.get_version_info()
            })
            
            # 更新性能统计
            self._update_performance_stats(processing_time, True)
            
            return result
            
        except Exception as e:
            # 错误处理
            processing_time = time.time() - start_time
            self._update_performance_stats(processing_time, False)
            
            logger.error(f"文书分类失败: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "documents": [],
                "statistics": {},
                "processing_time": round(processing_time, 3),
                "algorithm_version": "error",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _execute_classification(self, 
                                    raw_text: str, 
                                    version: ClassificationVersion, 
                                    options: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体的分类算法"""
        
        if version == ClassificationVersion.ADVANCED:
            # 使用先进版本
            return self.advanced_engine.classify_medical_text(raw_text, options)
            
        elif version == ClassificationVersion.ENHANCED:
            # 使用增强版本（现有的enhanced_classification_api逻辑）
            return await self._enhanced_classification(raw_text, options)
            
        elif version == ClassificationVersion.BASIC:
            # 使用基础版本
            return await self._basic_classification(raw_text, options)
            
        else:
            raise ValueError(f"不支持的分类版本: {version}")
    
    async def _enhanced_classification(self, raw_text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """增强版分类（复用现有逻辑）"""
        from ..enhanced_classification_api import perform_intelligent_classification
        
        confidence_threshold = options.get('confidence_threshold', 0.5)
        documents = perform_intelligent_classification(raw_text, confidence_threshold)
        
        return {
            "success": True,
            "documents": documents,
            "statistics": {
                "totalDocuments": len(documents),
                "averageConfidence": sum(doc.get("confidence", 0) for doc in documents) / max(len(documents), 1)
            },
            "total_documents": len(documents)
        }
    
    async def _basic_classification(self, raw_text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """基础版分类"""
        documents = []
        confidence_threshold = options.get('confidence_threshold', 0.5)
        
        # 简单的关键词匹配
        basic_rules = {
            "入院记录": ["入院记录", "入院", "主诉"],
            "病程记录": ["病程记录", "病程", "查房"],
            "手术记录": ["手术记录", "手术", "术中"],
            "出院记录": ["出院记录", "出院", "出院诊断"]
        }
        
        for doc_type, keywords in basic_rules.items():
            if any(keyword in raw_text for keyword in keywords):
                confidence = min(0.6 + len([k for k in keywords if k in raw_text]) * 0.1, 0.9)
                if confidence >= confidence_threshold:
                    documents.append({
                        "title": doc_type,
                        "category": doc_type.lower().replace("记录", "_record"),
                        "type": doc_type.lower().replace("记录", "_record"),
                        "confidence": confidence,
                        "content": raw_text[:200],
                        "summary": f"{doc_type}摘要"
                    })
        
        return {
            "success": True,
            "documents": documents,
            "statistics": {
                "totalDocuments": len(documents),
                "averageConfidence": sum(doc.get("confidence", 0) for doc in documents) / max(len(documents), 1)
            },
            "total_documents": len(documents)
        }
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """验证分类结果质量"""
        if not result.get("success", False):
            return False
        
        documents = result.get("documents", [])
        if not documents:
            return False
        
        # 检查置信度
        avg_confidence = sum(doc.get("confidence", 0) for doc in documents) / len(documents)
        if avg_confidence < 0.3:
            return False
        
        return True
    
    def _update_performance_stats(self, processing_time: float, success: bool):
        """更新性能统计"""
        if success:
            self.performance_stats["successful_requests"] += 1
        else:
            self.performance_stats["failed_requests"] += 1
        
        # 更新平均处理时间
        total_requests = self.performance_stats["total_requests"]
        current_avg = self.performance_stats["average_processing_time"]
        self.performance_stats["average_processing_time"] = \
            (current_avg * (total_requests - 1) + processing_time) / total_requests
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total = self.performance_stats["total_requests"]
        successful = self.performance_stats["successful_requests"]
        
        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": self.performance_stats["failed_requests"],
            "success_rate": round(successful / max(total, 1) * 100, 2),
            "average_processing_time": round(self.performance_stats["average_processing_time"], 3),
            "version_usage": self.performance_stats["version_usage"],
            "current_version": self.config.get_current_version().value
        }
    
    def reset_performance_stats(self):
        """重置性能统计"""
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_processing_time": 0.0,
            "version_usage": {}
        }
    
    async def switch_version(self, version: ClassificationVersion) -> Dict[str, Any]:
        """切换分类版本"""
        try:
            old_version = self.config.get_current_version()
            success = self.config.set_version(version)
            
            if success:
                return {
                    "success": True,
                    "message": f"成功从 {old_version.value} 切换到 {version.value}",
                    "old_version": old_version.value,
                    "new_version": version.value
                }
            else:
                return {
                    "success": False,
                    "message": "版本切换失败",
                    "current_version": old_version.value
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"版本切换失败: {str(e)}",
                "current_version": self.config.get_current_version().value
            }
    
    def get_version_info(self) -> Dict[str, Any]:
        """获取版本信息"""
        return self.config.get_version_info()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 测试分类功能
            test_text = "患者张三，男，45岁，因胸痛入院。"
            result = await self.classify_medical_text(test_text)
            
            config_validation = self.config.validate_config()
            
            return {
                "status": "healthy" if result["success"] and config_validation["valid"] else "unhealthy",
                "classification_test": result["success"],
                "config_validation": config_validation,
                "current_version": self.config.get_current_version().value,
                "performance_stats": self.get_performance_stats(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# 全局服务实例
unified_classification_service = UnifiedClassificationService()
