#!/usr/bin/env python3
"""
先进医疗文书分类引擎
基于MVP测试验证的高精度分类算法
支持多格式、多场景的医疗文书智能识别
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AdvancedClassificationEngine:
    """先进医疗文书分类引擎"""
    
    def __init__(self):
        """初始化分类引擎"""
        self.classification_rules = self._load_classification_rules()
        self.confidence_threshold = 0.5
        
    def _load_classification_rules(self) -> Dict[str, Any]:
        """加载分类规则配置"""
        return {
            "admission_record": {
                "keywords": ["入院记录", "入院", "主诉", "现病史", "既往史", "体格检查"],
                "patterns": [r'入\s*院\s*记\s*录', r'姓名[：:]\s*\w+', r'主诉[：:]'],
                "required_sections": ["主诉", "现病史"],
                "category": "admission_record",
                "base_confidence": 0.85
            },
            "progress_note": {
                "keywords": ["病程记录", "首次病程", "查房记录", "病情分析", "诊疗计划"],
                "patterns": [r'病程记录', r'查房记录', r'医师查房'],
                "required_sections": ["病程", "诊疗"],
                "category": "progress_note", 
                "base_confidence": 0.80
            },
            "operation_record": {
                "keywords": ["手术记录", "手术", "术前", "术后", "手术经过", "术中所见"],
                "patterns": [r'手术记录', r'手术日期[：:]', r'手术名称[：:]', r'手术经过[：:]'],
                "required_sections": ["手术", "术中"],
                "category": "operation_record",
                "base_confidence": 0.90
            },
            "examination_report": {
                "keywords": ["检查记录", "CT检查", "MRI检查", "X光", "超声", "心电图"],
                "patterns": [r'检查记录', r'CT.*?检查', r'MRI.*?检查'],
                "required_sections": ["检查"],
                "category": "examination_report",
                "base_confidence": 0.85
            },
            "nursing_document": {
                "keywords": ["护理记录", "护理", "体温单", "护理措施", "观察记录"],
                "patterns": [r'护理记录', r'体温.*?℃', r'血压.*?mmHg'],
                "required_sections": ["护理"],
                "category": "nursing_document",
                "base_confidence": 0.75
            },
            "medical_order": {
                "keywords": ["医嘱", "长期医嘱", "临时医嘱", "治疗方案", "用药"],
                "patterns": [r'医嘱', r'长期医嘱', r'临时医嘱', r'治疗方案[：:]'],
                "required_sections": ["医嘱", "治疗"],
                "category": "medical_order",
                "base_confidence": 0.80
            },
            "discharge_record": {
                "keywords": ["出院记录", "出院", "出院诊断", "出院医嘱", "出院指导"],
                "patterns": [r'出院记录', r'出院诊断[：:]', r'出院医嘱[：:]'],
                "required_sections": ["出院"],
                "category": "discharge_record",
                "base_confidence": 0.85
            }
        }
    
    def classify_medical_text(self, raw_text: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        对医疗文本进行智能分类
        
        Args:
            raw_text: 原始医疗文本
            options: 分类选项配置
            
        Returns:
            分类结果字典
        """
        start_time = datetime.now()
        
        try:
            # 解析选项
            options = options or {}
            confidence_threshold = options.get('confidence_threshold', self.confidence_threshold)
            enable_advanced_features = options.get('enable_advanced_features', True)
            
            # 执行分类
            documents = []
            
            if enable_advanced_features:
                # 使用先进算法
                documents = self._advanced_classification(raw_text, confidence_threshold)
            else:
                # 使用基础算法
                documents = self._basic_classification(raw_text, confidence_threshold)
            
            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 生成统计信息
            statistics = self._calculate_statistics(documents, processing_time)
            
            return {
                "success": True,
                "documents": documents,
                "statistics": statistics,
                "processing_time": processing_time,
                "algorithm_version": "advanced" if enable_advanced_features else "basic",
                "total_documents": len(documents)
            }
            
        except Exception as e:
            logger.error(f"文书分类失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "documents": [],
                "statistics": {},
                "processing_time": 0
            }
    
    def _advanced_classification(self, text: str, confidence_threshold: float) -> List[Dict[str, Any]]:
        """先进分类算法（基于MVP测试验证）"""
        documents = []
        
        # 1. 首次病程记录识别
        if self._match_document_type(text, "progress_note", "首次病程记录"):
            content = self._extract_section_between_markers(text, '首次病程记录', '查房记录', 1500)
            confidence = self._calculate_advanced_confidence(text, "progress_note")
            if confidence >= confidence_threshold:
                documents.append({
                    "title": "首次病程记录",
                    "category": "progress_note",
                    "type": "first_progress_note",
                    "confidence": confidence,
                    "content": content,
                    "summary": self._generate_summary(content, "首次病程记录"),
                    "position": {"startMarker": "首次病程记录", "endMarker": "查房记录"}
                })
        
        # 2. 查房记录识别（支持多次查房）
        rounds = self._find_all_rounds(text)
        for round_info in rounds:
            confidence = self._calculate_advanced_confidence(round_info['content'], "progress_note")
            if confidence >= confidence_threshold:
                documents.append({
                    "title": f"{round_info['doctor']}查房记录",
                    "category": "progress_note", 
                    "type": "attending_progress",
                    "confidence": confidence,
                    "content": round_info['content'],
                    "summary": f"{round_info['doctor']}于{round_info['time']}查房",
                    "position": {
                        "startMarker": round_info['marker'],
                        "line_number": round_info['line_number']
                    }
                })
        
        # 3. 手术记录识别（多模式识别）
        surgery_record = self._extract_surgery_record(text)
        if surgery_record:
            confidence = self._calculate_advanced_confidence(surgery_record, "operation_record")
            if confidence >= confidence_threshold:
                documents.append({
                    "title": "手术记录",
                    "category": "operation_record",
                    "type": "operation_record", 
                    "confidence": confidence,
                    "content": surgery_record,
                    "summary": self._extract_surgery_summary(surgery_record),
                    "position": {"startMarker": "手术日期", "endMarker": "术者签名"}
                })
        
        # 4. 检查记录识别
        for check_type in ["CT检查记录", "核磁检查记录", "超声检查"]:
            if check_type in text:
                content = self._extract_section_between_markers(text, check_type, "医师签名", 400)
                confidence = self._calculate_advanced_confidence(content, "examination_report")
                if confidence >= confidence_threshold:
                    documents.append({
                        "title": check_type,
                        "category": "examination_report",
                        "type": "imaging_examination",
                        "confidence": confidence,
                        "content": content,
                        "summary": f"{check_type}结果",
                        "position": {"startMarker": check_type, "endMarker": "医师签名"}
                    })
        
        # 5. 术前讨论记录识别
        if "术前讨论记录" in text:
            content = self._extract_section_between_markers(text, "术前讨论记录", "术前小结", 1000)
            confidence = self._calculate_advanced_confidence(content, "operation_record")
            if confidence >= confidence_threshold:
                documents.append({
                    "title": "术前讨论记录",
                    "category": "operation_record",
                    "type": "preoperative_discussion",
                    "confidence": confidence,
                    "content": content,
                    "summary": "多学科术前讨论，制定手术方案",
                    "position": {"startMarker": "术前讨论记录", "endMarker": "术前小结"}
                })
        
        return documents
    
    def _basic_classification(self, text: str, confidence_threshold: float) -> List[Dict[str, Any]]:
        """基础分类算法（兼容现有系统）"""
        documents = []
        
        for doc_type, rules in self.classification_rules.items():
            if self._match_document_type(text, doc_type):
                confidence = self._calculate_basic_confidence(text, rules)
                if confidence >= confidence_threshold:
                    content = self._extract_basic_content(text, rules['keywords'])
                    documents.append({
                        "title": self._get_document_title(doc_type),
                        "category": rules['category'],
                        "type": doc_type,
                        "confidence": confidence,
                        "content": content,
                        "summary": self._generate_basic_summary(content, doc_type)
                    })
        
        return documents
    
    def _match_document_type(self, text: str, doc_type: str, specific_title: str = None) -> bool:
        """匹配文档类型"""
        if specific_title and specific_title in text:
            return True
            
        rules = self.classification_rules.get(doc_type, {})
        keywords = rules.get('keywords', [])
        patterns = rules.get('patterns', [])
        
        # 关键词匹配
        keyword_matches = sum(1 for keyword in keywords if keyword in text)
        
        # 正则模式匹配
        pattern_matches = sum(1 for pattern in patterns if re.search(pattern, text))
        
        return keyword_matches >= 2 or pattern_matches >= 1
    
    def _calculate_advanced_confidence(self, text: str, doc_type: str) -> float:
        """计算先进置信度"""
        rules = self.classification_rules.get(doc_type, {})
        base_confidence = rules.get('base_confidence', 0.7)
        
        # 关键词密度
        keywords = rules.get('keywords', [])
        keyword_density = sum(text.lower().count(kw.lower()) for kw in keywords) / len(text) * 1000
        
        # 模式匹配强度
        patterns = rules.get('patterns', [])
        pattern_strength = sum(1 for pattern in patterns if re.search(pattern, text)) / max(len(patterns), 1)
        
        # 文本长度调整
        length_factor = min(len(text) / 200, 1.2) if len(text) > 100 else 0.8
        
        # 综合计算
        confidence = base_confidence + (keyword_density * 0.1) + (pattern_strength * 0.1)
        confidence *= length_factor
        
        return min(round(confidence, 2), 0.98)
    
    def _calculate_basic_confidence(self, text: str, rules: Dict[str, Any]) -> float:
        """计算基础置信度"""
        keywords = rules.get('keywords', [])
        base_confidence = rules.get('base_confidence', 0.7)
        
        keyword_count = sum(1 for keyword in keywords if keyword in text.lower())
        confidence = base_confidence + (keyword_count * 0.05)
        
        return min(round(confidence, 2), 0.95)
    
    def _extract_section_between_markers(self, text: str, start_marker: str, end_marker: str, max_length: int = 1000) -> str:
        """提取两个标记之间的文本段落"""
        lines = text.split('\n')
        start_idx = -1
        end_idx = len(lines)
        
        # 找到开始标记
        for i, line in enumerate(lines):
            if start_marker in line:
                start_idx = i
                break
        
        if start_idx == -1:
            return ""
        
        # 找到结束标记
        for i in range(start_idx + 1, len(lines)):
            if end_marker in lines[i]:
                end_idx = i
                break
        
        # 提取内容
        section_lines = lines[start_idx:end_idx]
        content = '\n'.join(section_lines)
        
        return content[:max_length] if len(content) > max_length else content
    
    def _find_all_rounds(self, text: str) -> List[Dict[str, Any]]:
        """查找所有查房记录"""
        rounds = []
        lines = text.split('\n')
        
        round_patterns = [
            r'.*查房记录',
            r'.*医师查房',
            r'.*主任.*查房',
            r'.*主治.*查房'
        ]
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for pattern in round_patterns:
                if re.search(pattern, line_stripped):
                    # 提取医师信息
                    doctor_match = re.search(r'([^0-9\s]+(?:主任|主治|副主任).*?医师)', line_stripped)
                    doctor = doctor_match.group(1) if doctor_match else '医师未识别'
                    
                    # 提取时间信息
                    time_match = re.search(r'(\d{4}[-年]\d{2}[-月]\d{2})', line_stripped)
                    time = time_match.group(1) if time_match else '时间未识别'
                    
                    # 提取内容
                    content = self._extract_round_content(text, i)
                    
                    rounds.append({
                        'line_number': i + 1,
                        'marker': line_stripped,
                        'doctor': doctor,
                        'time': time,
                        'content': content
                    })
                    break
        
        return rounds
    
    def _extract_round_content(self, text: str, line_number: int, max_lines: int = 10) -> str:
        """提取查房记录内容"""
        lines = text.split('\n')
        start_idx = line_number
        
        content_lines = []
        for i in range(start_idx, min(start_idx + max_lines, len(lines))):
            line = lines[i].strip()
            if line:
                content_lines.append(line)
                # 如果遇到下一个时间标记，停止
                if i > start_idx and re.search(r'\d{4}[-年]\d{2}[-月]\d{2}', line):
                    break
        
        return '\n'.join(content_lines)
    
    def _extract_surgery_record(self, text: str) -> Optional[str]:
        """提取手术记录"""
        if not ('手术日期：' in text and '手术名称：' in text and '手术经过：' in text):
            return None
            
        lines = text.split('\n')
        surgery_start = -1
        surgery_end = len(lines)
        
        # 查找手术记录开始位置
        for i, line in enumerate(lines):
            if '手术日期：' in line:
                surgery_start = i - 1 if i > 0 else i
                break
        
        if surgery_start == -1:
            return None
        
        # 查找手术记录结束位置
        for i in range(surgery_start + 1, len(lines)):
            if '术者签名：' in lines[i]:
                surgery_end = i + 1
                break
        
        # 提取手术记录内容
        surgery_lines = lines[surgery_start:surgery_end]
        return '\n'.join(surgery_lines)
    
    def _extract_surgery_summary(self, surgery_content: str) -> str:
        """提取手术摘要"""
        # 提取手术名称
        name_match = re.search(r'手术名称[：:]\s*([^\n]+)', surgery_content)
        surgery_name = name_match.group(1) if name_match else '手术'
        
        return f"{surgery_name}，手术顺利完成"
    
    def _extract_basic_content(self, text: str, keywords: List[str], max_length: int = 200) -> str:
        """提取基础内容"""
        lines = text.split('\n')
        
        for keyword in keywords:
            for i, line in enumerate(lines):
                if keyword in line:
                    section_lines = []
                    for j in range(i, min(i + 5, len(lines))):
                        section_lines.append(lines[j])
                        if len('\n'.join(section_lines)) > max_length:
                            break
                    return '\n'.join(section_lines)[:max_length]
        
        return text[:max_length]
    
    def _generate_summary(self, content: str, doc_type: str) -> str:
        """生成文档摘要"""
        if not content:
            return f"{doc_type}摘要"
            
        # 提取关键信息生成摘要
        if "患者" in content:
            patient_match = re.search(r'患者([^，,]+)', content)
            if patient_match:
                return f"患者{patient_match.group(1)}的{doc_type}"
        
        return f"{doc_type}，包含{len(content)}字符的详细信息"
    
    def _generate_basic_summary(self, content: str, doc_type: str) -> str:
        """生成基础摘要"""
        type_names = {
            "admission_record": "入院记录",
            "progress_note": "病程记录", 
            "operation_record": "手术记录",
            "examination_report": "检查报告",
            "nursing_document": "护理文书",
            "medical_order": "医嘱记录",
            "discharge_record": "出院记录"
        }
        
        return f"{type_names.get(doc_type, doc_type)}摘要"
    
    def _get_document_title(self, doc_type: str) -> str:
        """获取文档标题"""
        titles = {
            "admission_record": "入院记录",
            "progress_note": "病程记录",
            "operation_record": "手术记录", 
            "examination_report": "检查报告",
            "nursing_document": "护理记录",
            "medical_order": "医嘱记录",
            "discharge_record": "出院记录"
        }
        
        return titles.get(doc_type, doc_type)
    
    def _calculate_statistics(self, documents: List[Dict[str, Any]], processing_time: float) -> Dict[str, Any]:
        """计算统计信息"""
        if not documents:
            return {
                "totalDocuments": 0,
                "averageConfidence": 0,
                "processingTime": processing_time,
                "categoryDistribution": {}
            }
        
        total_docs = len(documents)
        avg_confidence = sum(doc.get("confidence", 0) for doc in documents) / total_docs
        
        # 分类分布统计
        category_dist = {}
        for doc in documents:
            category = doc.get("category", "unknown")
            category_dist[category] = category_dist.get(category, 0) + 1
        
        return {
            "totalDocuments": total_docs,
            "averageConfidence": round(avg_confidence, 3),
            "processingTime": processing_time,
            "categoryDistribution": category_dist,
            "highConfidenceCount": sum(1 for doc in documents if doc.get("confidence", 0) >= 0.8),
            "lowConfidenceCount": sum(1 for doc in documents if doc.get("confidence", 0) < 0.6)
        }
