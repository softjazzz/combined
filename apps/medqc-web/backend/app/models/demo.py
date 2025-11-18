"""
Demo 反馈系统数据库模型
用于持久化存储 LX33 质控规则反馈记录
"""

from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Feedback(Base):
    """反馈记录模型"""
    __tablename__ = "feedbacks"

    # 主键
    feedback_id = Column(String(36), primary_key=True, index=True, comment="反馈ID")

    # 评估相关
    evaluation_id = Column(String(36), nullable=True, comment="评估记录ID")
    rule_id = Column(String(50), nullable=False, index=True, comment="规则ID")
    rule_code = Column(String(50), nullable=False, index=True, comment="规则编号")
    rule_name = Column(String(200), nullable=False, comment="规则名称")
    document_name = Column(String(200), nullable=False, comment="文档名称")

    # 评估结果
    evaluation_result = Column(Boolean, nullable=False, index=True, comment="评估结果（True=合规，False=不合规）")

    # 反馈信息
    feedback_type = Column(String(20), nullable=False, index=True, comment="反馈类型（correct/incorrect）")
    error_category = Column(String(50), nullable=True, index=True, comment="错误类别")
    error_detail = Column(Text, nullable=True, comment="错误详情")
    evidence = Column(Text, nullable=True, comment="补充证据")
    feedback_by = Column(String(100), nullable=True, comment="反馈人")

    # 病历原文
    medical_text = Column(Text, nullable=True, comment="进行质控的病历原文")

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True, comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "feedback_id": self.feedback_id,
            "evaluation_id": self.evaluation_id,
            "rule_id": self.rule_id,
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "document_name": self.document_name,
            "evaluation_result": self.evaluation_result,
            "feedback_type": self.feedback_type,
            "error_category": self.error_category,
            "error_detail": self.error_detail,
            "evidence": self.evidence,
            "feedback_by": self.feedback_by,
            "medical_text": self.medical_text,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None
        }
