# -*- coding: utf-8 -*-
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory users (migrated from legacy main_api.py)
users_db = {
    "admin@medqc.com": {
        "id": "admin-001",
        "email": "admin@medqc.com",
        "display_name": "\u7cfb\u7edf\u7ba1\u7406\u5458",
        "department": "\u7cfb\u7edf\u7ba1\u7406\u90e8",
        "roles": ["admin", "qc_manager"],
        "password_hash": pwd_context.hash("admin888"),
        "avatar": "",
        "phone": "13800138000",
        "bio": "\u7cfb\u7edf\u7ba1\u7406\u5458\uff0c\u8d1f\u8d23\u6574\u4e2a\u533b\u7597\u8d28\u63a7\u7cfb\u7edf\u7684\u8fd0\u7ef4\u548c\u7ba1\u7406\u5de5\u4f5c\u3002",
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None,
    },
    "qc@medqc.com": {
        "id": "qc-001",
        "email": "qc@medqc.com",
        "display_name": "\u8d28\u63a7\u4e3b\u7ba1",
        "department": "\u8d28\u63a7\u79d1",
        "roles": ["qc_manager"],
        "password_hash": pwd_context.hash("qc123456"),
        "avatar": "",
        "phone": "13800138001",
        "bio": "\u8d28\u63a7\u79d1\u4e3b\u7ba1\uff0c\u4e13\u6ce8\u4e8e\u533b\u7597\u8d28\u91cf\u63a7\u5236\u548c\u75c5\u6848\u5ba1\u6838\u5de5\u4f5c\u3002",
        "created_at": "2024-01-15T00:00:00Z",
        "last_login": None,
    },
    "doctor@medqc.com": {
        "id": "doctor-001",
        "email": "doctor@medqc.com",
        "display_name": "\u4e34\u5e8a\u533b\u751f",
        "department": "\u5185\u79d1",
        "roles": ["doctor"],
        "password_hash": pwd_context.hash("doctor123"),
        "avatar": "",
        "phone": "13800138002",
        "bio": "\u5185\u79d1\u533b\u751f\uff0c\u4ece\u4e8b\u4e34\u5e8a\u8bca\u7597\u548c\u75c5\u6848\u8bb0\u5f55\u5de5\u4f5c\u3002",
        "created_at": "2024-02-01T00:00:00Z",
        "last_login": None,
    },
}

# In-memory medical records (simple seed for dev)
medical_records_db = {}

def _seed_records():
    from datetime import datetime, timedelta
    for i in range(1, 6):
        rid = f"record-{i:03d}"
        medical_records_db[rid] = {
            "id": rid,
            "patient_name": f"\u60a3\u8005{i:02d}",
            "patient_age": 30 + (i % 50),
            "patient_gender": "male" if i % 2 == 0 else "female",
            "department": ["\u5185\u79d1", "\u5916\u79d1", "\u513f\u79d1", "\u5987\u79d1", "\u9aa8\u79d1"][i % 5],
            "admission_date": (datetime.utcnow()).strftime("%Y-%m-%d"),
            "record_type": ["inpatient", "outpatient", "emergency"][i % 3],
            "content": "\u793a\u4f8b\u75c5\u6848\u8bb0\u5f55",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "created_by": "doctor-001",
            "file_url": None,
        }

_seed_records()

# QC in-memory stores
qc_results_db = {}
qc_rules_db = {
    "rule-001": {
        "id": "rule-001",
        "rule_code": "QC001",
        "name": "\u4e3b\u8bc9\u5b8c\u6574\u6027\u68c0\u67e5",
        "description": "\u68c0\u67e5\u75c5\u6848\u4e2d\u4e3b\u8bc9\u90e8\u5206\u662f\u5426\u5b8c\u6574\uff0c\u5305\u542b\u60a3\u8005\u4e3b\u8981\u75c7\u72b6\u548c\u6301\u7eed\u65f6\u95f4",
        "category": "\u57fa\u672c\u4fe1\u606f",
        "severity": "major",
        "weight": 10,
        "is_active": True,
        "conditions": "content.includes('\u4e3b\u8bc9') && content.match(/\\\\d+[\u5929\u65e5\u6708\u5e74]/)",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T15:30:00Z",
        "execution_count": 1250,
        "pass_rate": 85.0,
        "issue_count": 187,
    },
    "rule-002": {
        "id": "rule-002",
        "rule_code": "QC002",
        "name": "\u8bca\u65ad\u4f9d\u636e\u5145\u5206\u6027",
        "description": "\u68c0\u67e5\u8bca\u65ad\u662f\u5426\u6709\u5145\u5206\u7684\u4f9d\u636e\u652f\u6491\uff0c\u5305\u62ec\u75c7\u72b6\u3001\u4f53\u5f81\u3001\u68c0\u67e5\u7ed3\u679c\u7b49",
        "category": "\u8bca\u65ad\u8d28\u91cf",
        "severity": "critical",
        "weight": 15,
        "is_active": True,
        "conditions": "diagnosis.length > 0 && evidence.length >= 3",
        "created_at": "2024-01-10T09:00:00Z",
        "updated_at": "2024-01-25T11:45:00Z",
        "execution_count": 980,
        "pass_rate": 78.0,
        "issue_count": 215,
    },
}

# LLM configs in-memory
llm_configs = {
    "cfg-001": {
        "id": "cfg-001",
        "name": "Aliyun Qwen 2.5 14B",
        "provider": "aliyun",
        "model": "qwen2.5-14b-instruct",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }
}

# Demo feedback storage (for LX33 demo page)
demo_feedbacks_db = {}
