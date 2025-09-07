#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
病历文书内容分离器
将整本病历按文书类型智能分离，为分文书质控提供基础
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DocumentSection:
    """文书段落数据结构"""
    document_type: str
    content: str
    start_position: int
    end_position: int
    confidence: float
    keywords_found: List[str]

class DocumentSeparator:
    """病历文书智能分离器"""
    
    def __init__(self):
        # 文书类型识别规则
        self.document_patterns = {
            '入院记录': {
                'keywords': ['入院记录', '主诉', '现病史', '既往史', '个人史', '家族史', '体格检查', '入院诊断'],
                'start_markers': ['入院记录', '住院病历', '入院病历'],
                'end_markers': ['病程记录', '首次病程记录', '医师查房记录'],
                'required_keywords': ['主诉', '现病史'],
                'weight': 1.0
            },
            '病程记录': {
                'keywords': ['病程记录', '日常病程', '主治医师查房', '上级医师查房', '病情变化', '治疗方案'],
                'start_markers': ['病程记录', '首次病程记录', '日常病程记录'],
                'end_markers': ['手术记录', '出院记录', '死亡记录'],
                'required_keywords': ['病程', '治疗'],
                'weight': 1.0
            },
            '手术记录': {
                'keywords': ['手术记录', '术前诊断', '术后诊断', '手术过程', '麻醉方式', '手术步骤', '术中情况'],
                'start_markers': ['手术记录', '手术操作记录'],
                'end_markers': ['术后病程', '病程记录', '出院记录'],
                'required_keywords': ['手术', '术'],
                'weight': 1.2
            },
            '出院记录': {
                'keywords': ['出院记录', '出院诊断', '入院情况', '诊疗经过', '出院情况', '出院医嘱', '随访'],
                'start_markers': ['出院记录', '出院小结'],
                'end_markers': ['死亡记录', '病案首页'],
                'required_keywords': ['出院'],
                'weight': 1.1
            }
        }
        
        # 通用分隔符
        self.section_separators = [
            r'\n\s*={3,}\s*\n',  # ===分隔线
            r'\n\s*-{3,}\s*\n',  # ---分隔线
            r'\n\s*\*{3,}\s*\n', # ***分隔线
            r'\n\s*#{3,}\s*\n',  # ###分隔线
        ]
    
    def separate_document(self, content: str) -> Dict[str, DocumentSection]:
        """
        将整本病历分离为不同文书类型的内容
        
        Args:
            content: 完整的病历内容
            
        Returns:
            Dict[str, DocumentSection]: 按文书类型分组的内容
        """
        logger.info("🔍 开始病历文书智能分离...")
        
        # 1. 预处理内容
        cleaned_content = self._preprocess_content(content)
        
        # 2. 基于标记的分离
        sections = self._separate_by_markers(cleaned_content)
        
        # 3. 基于关键词的分类
        classified_sections = self._classify_sections(sections)
        
        # 4. 内容验证和优化
        validated_sections = self._validate_and_optimize(classified_sections)
        
        logger.info(f"✅ 文书分离完成，识别到 {len(validated_sections)} 种文书类型")
        for doc_type, section in validated_sections.items():
            logger.info(f"  📋 {doc_type}: {len(section.content)}字符 (置信度: {section.confidence:.2f})")
        
        return validated_sections
    
    def _preprocess_content(self, content: str) -> str:
        """预处理病历内容"""
        # 统一换行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除多余空白
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # 标准化常见标题格式
        content = re.sub(r'(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})', r'\n\1 \2', content)
        
        return content.strip()
    
    def _separate_by_markers(self, content: str) -> List[Tuple[str, int, int]]:
        """基于标记分离文档段落"""
        sections = []
        
        # 查找所有可能的分隔点
        split_points = [0]  # 开始位置
        
        for doc_type, patterns in self.document_patterns.items():
            for marker in patterns['start_markers']:
                for match in re.finditer(rf'\b{re.escape(marker)}\b', content, re.IGNORECASE):
                    split_points.append(match.start())
        
        # 添加结束位置
        split_points.append(len(content))
        split_points = sorted(set(split_points))
        
        # 创建段落
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]
            section_content = content[start:end].strip()
            
            if len(section_content) > 50:  # 过滤太短的段落
                sections.append((section_content, start, end))
        
        return sections
    
    def _classify_sections(self, sections: List[Tuple[str, int, int]]) -> Dict[str, DocumentSection]:
        """基于关键词分类段落"""
        classified = {}
        
        for section_content, start_pos, end_pos in sections:
            best_match = self._find_best_document_type(section_content)
            
            if best_match:
                doc_type, confidence, keywords_found = best_match
                
                # 如果已存在该类型，合并内容
                if doc_type in classified:
                    existing = classified[doc_type]
                    if confidence > existing.confidence:
                        # 替换为更高置信度的内容
                        classified[doc_type] = DocumentSection(
                            document_type=doc_type,
                            content=section_content,
                            start_position=start_pos,
                            end_position=end_pos,
                            confidence=confidence,
                            keywords_found=keywords_found
                        )
                    else:
                        # 合并内容
                        existing.content += f"\n\n{section_content}"
                        existing.end_position = end_pos
                        existing.keywords_found.extend(keywords_found)
                        existing.keywords_found = list(set(existing.keywords_found))
                else:
                    classified[doc_type] = DocumentSection(
                        document_type=doc_type,
                        content=section_content,
                        start_position=start_pos,
                        end_position=end_pos,
                        confidence=confidence,
                        keywords_found=keywords_found
                    )
        
        return classified
    
    def _find_best_document_type(self, content: str) -> Optional[Tuple[str, float, List[str]]]:
        """为内容段落找到最佳的文书类型匹配"""
        content_lower = content.lower()
        best_score = 0
        best_type = None
        best_keywords = []
        
        for doc_type, patterns in self.document_patterns.items():
            score = 0
            found_keywords = []
            
            # 检查关键词
            for keyword in patterns['keywords']:
                if keyword.lower() in content_lower:
                    score += patterns['weight']
                    found_keywords.append(keyword)
            
            # 检查必需关键词
            required_found = 0
            for required in patterns['required_keywords']:
                if required.lower() in content_lower:
                    required_found += 1
            
            # 必需关键词权重更高
            if required_found > 0:
                score += required_found * patterns['weight'] * 2
            
            # 检查开始标记
            for marker in patterns['start_markers']:
                if marker.lower() in content_lower[:200]:  # 只检查前200字符
                    score += patterns['weight'] * 3
                    found_keywords.append(marker)
            
            if score > best_score:
                best_score = score
                best_type = doc_type
                best_keywords = found_keywords
        
        if best_score > 0:
            # 计算置信度 (0-1)
            max_possible_score = len(self.document_patterns[best_type]['keywords']) * \
                               self.document_patterns[best_type]['weight'] + \
                               len(self.document_patterns[best_type]['required_keywords']) * \
                               self.document_patterns[best_type]['weight'] * 2 + \
                               len(self.document_patterns[best_type]['start_markers']) * \
                               self.document_patterns[best_type]['weight'] * 3
            
            confidence = min(best_score / max_possible_score, 1.0)
            
            # 最低置信度阈值
            if confidence >= 0.1:
                return best_type, confidence, best_keywords
        
        return None
    
    def _validate_and_optimize(self, sections: Dict[str, DocumentSection]) -> Dict[str, DocumentSection]:
        """验证和优化分离结果"""
        validated = {}
        
        for doc_type, section in sections.items():
            # 内容长度验证
            if len(section.content.strip()) < 100:
                logger.warning(f"⚠️ {doc_type} 内容过短 ({len(section.content)}字符)，可能分离不准确")
                continue
            
            # 置信度验证
            if section.confidence < 0.2:
                logger.warning(f"⚠️ {doc_type} 置信度过低 ({section.confidence:.2f})，跳过")
                continue
            
            # 内容清理
            cleaned_content = self._clean_section_content(section.content)
            section.content = cleaned_content
            
            validated[doc_type] = section
        
        return validated
    
    def _clean_section_content(self, content: str) -> str:
        """清理段落内容"""
        # 移除多余的空白行
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # 移除页眉页脚信息
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # 跳过页码、日期戳等
            if re.match(r'^\d+$', line):  # 纯数字行（页码）
                continue
            if re.match(r'^第\s*\d+\s*页', line):  # 页码标识
                continue
            if len(line) > 0:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def get_document_types_summary(self, sections: Dict[str, DocumentSection]) -> Dict[str, Dict]:
        """获取文书类型摘要信息"""
        summary = {}
        
        for doc_type, section in sections.items():
            summary[doc_type] = {
                'content_length': len(section.content),
                'confidence': section.confidence,
                'keywords_found': section.keywords_found,
                'word_count': len(section.content.replace(' ', '').replace('\n', '')),
                'line_count': len(section.content.split('\n'))
            }
        
        return summary
