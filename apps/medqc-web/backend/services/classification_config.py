#!/usr/bin/env python3
"""
医疗文书分类配置管理器
支持动态切换分类算法版本
"""

import os
import json
from typing import Dict, Any, Optional
from enum import Enum

class ClassificationVersion(Enum):
    """分类算法版本枚举"""
    BASIC = "basic"           # 基础版本（现有系统）
    ENHANCED = "enhanced"     # 增强版本（现有enhanced_classification_api）
    ADVANCED = "advanced"     # 先进版本（新开发的高精度版本）

class ClassificationConfig:
    """分类配置管理器"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.config_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'classification_config.json')
        self.default_config = self._get_default_config()
        self.config = self._load_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "version": ClassificationVersion.ENHANCED.value,  # 默认使用增强版本
            "fallback_version": ClassificationVersion.BASIC.value,  # 失败时回退版本
            "confidence_threshold": 0.5,
            "enable_advanced_features": True,
            "enable_multi_round_detection": True,
            "enable_surgery_record_detection": True,
            "enable_examination_report_detection": True,
            "max_processing_time": 30.0,  # 最大处理时间（秒）
            "debug_mode": False,
            "performance_monitoring": True,
            "algorithm_settings": {
                "basic": {
                    "confidence_threshold": 0.5,
                    "max_documents": 10
                },
                "enhanced": {
                    "confidence_threshold": 0.5,
                    "enable_hierarchical_classification": True
                },
                "advanced": {
                    "confidence_threshold": 0.5,
                    "enable_advanced_features": True,
                    "enable_multi_round_detection": True,
                    "enable_surgery_record_detection": True,
                    "max_rounds": 20
                }
            }
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
            else:
                return self.default_config.copy()
        except Exception as e:
            print(f"加载配置文件失败，使用默认配置: {str(e)}")
            return self.default_config.copy()
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False
    
    def get_current_version(self) -> ClassificationVersion:
        """获取当前使用的分类版本"""
        version_str = self.config.get("version", ClassificationVersion.ENHANCED.value)
        try:
            return ClassificationVersion(version_str)
        except ValueError:
            return ClassificationVersion.ENHANCED
    
    def set_version(self, version: ClassificationVersion) -> bool:
        """设置分类版本"""
        try:
            self.config["version"] = version.value
            return self.save_config()
        except Exception as e:
            print(f"设置版本失败: {str(e)}")
            return False
    
    def get_fallback_version(self) -> ClassificationVersion:
        """获取回退版本"""
        version_str = self.config.get("fallback_version", ClassificationVersion.BASIC.value)
        try:
            return ClassificationVersion(version_str)
        except ValueError:
            return ClassificationVersion.BASIC
    
    def get_confidence_threshold(self, version: Optional[ClassificationVersion] = None) -> float:
        """获取置信度阈值"""
        if version is None:
            version = self.get_current_version()
        
        algorithm_settings = self.config.get("algorithm_settings", {})
        version_settings = algorithm_settings.get(version.value, {})
        
        return version_settings.get("confidence_threshold", 
                                  self.config.get("confidence_threshold", 0.5))
    
    def get_algorithm_settings(self, version: Optional[ClassificationVersion] = None) -> Dict[str, Any]:
        """获取算法设置"""
        if version is None:
            version = self.get_current_version()
        
        algorithm_settings = self.config.get("algorithm_settings", {})
        version_settings = algorithm_settings.get(version.value, {})
        
        # 合并全局设置
        global_settings = {
            "confidence_threshold": self.config.get("confidence_threshold", 0.5),
            "enable_advanced_features": self.config.get("enable_advanced_features", True),
            "enable_multi_round_detection": self.config.get("enable_multi_round_detection", True),
            "enable_surgery_record_detection": self.config.get("enable_surgery_record_detection", True),
            "enable_examination_report_detection": self.config.get("enable_examination_report_detection", True),
            "debug_mode": self.config.get("debug_mode", False)
        }
        
        global_settings.update(version_settings)
        return global_settings
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查功能是否启用"""
        return self.config.get(feature_name, False)
    
    def get_max_processing_time(self) -> float:
        """获取最大处理时间"""
        return self.config.get("max_processing_time", 30.0)
    
    def is_debug_mode(self) -> bool:
        """是否为调试模式"""
        return self.config.get("debug_mode", False)
    
    def is_performance_monitoring_enabled(self) -> bool:
        """是否启用性能监控"""
        return self.config.get("performance_monitoring", True)
    
    def update_setting(self, key: str, value: Any) -> bool:
        """更新单个设置"""
        try:
            self.config[key] = value
            return self.save_config()
        except Exception as e:
            print(f"更新设置失败: {str(e)}")
            return False
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        try:
            self.config = self.default_config.copy()
            return self.save_config()
        except Exception as e:
            print(f"重置配置失败: {str(e)}")
            return False
    
    def get_version_info(self) -> Dict[str, Any]:
        """获取版本信息"""
        current_version = self.get_current_version()
        fallback_version = self.get_fallback_version()
        
        return {
            "current_version": current_version.value,
            "current_version_name": self._get_version_name(current_version),
            "fallback_version": fallback_version.value,
            "fallback_version_name": self._get_version_name(fallback_version),
            "available_versions": [v.value for v in ClassificationVersion],
            "version_descriptions": self._get_version_descriptions()
        }
    
    def _get_version_name(self, version: ClassificationVersion) -> str:
        """获取版本名称"""
        names = {
            ClassificationVersion.BASIC: "基础版本",
            ClassificationVersion.ENHANCED: "增强版本", 
            ClassificationVersion.ADVANCED: "先进版本"
        }
        return names.get(version, "未知版本")
    
    def _get_version_descriptions(self) -> Dict[str, str]:
        """获取版本描述"""
        return {
            ClassificationVersion.BASIC.value: "基础关键词匹配算法，稳定可靠",
            ClassificationVersion.ENHANCED.value: "增强版分类算法，支持层级化分类",
            ClassificationVersion.ADVANCED.value: "先进智能分类算法，支持多格式识别和高精度分类"
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置有效性"""
        issues = []
        warnings = []
        
        # 检查版本有效性
        try:
            current_version = self.get_current_version()
        except:
            issues.append("当前版本配置无效")
        
        # 检查置信度阈值
        confidence_threshold = self.config.get("confidence_threshold", 0.5)
        if not (0.0 <= confidence_threshold <= 1.0):
            issues.append("置信度阈值必须在0.0-1.0之间")
        
        # 检查处理时间限制
        max_time = self.config.get("max_processing_time", 30.0)
        if max_time <= 0:
            issues.append("最大处理时间必须大于0")
        elif max_time > 300:
            warnings.append("最大处理时间过长，可能影响用户体验")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }

# 全局配置实例
classification_config = ClassificationConfig()
