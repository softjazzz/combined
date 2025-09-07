from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory users (migrated from legacy main_api.py)
users_db = {
    "admin@medqc.com": {
        "id": "admin-001",
        "email": "admin@medqc.com",
        "display_name": "系统管理员",
        "department": "系统管理部",
        "roles": ["admin", "qc_manager"],
        "password_hash": pwd_context.hash("admin123"),
        "avatar": "",
        "phone": "13800138000",
        "bio": "系统管理员，负责整个医疗质控系统的运维和管理工作。",
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None,
    },
    "qc@medqc.com": {
        "id": "qc-001",
        "email": "qc@medqc.com",
        "display_name": "质控主管",
        "department": "质控科",
        "roles": ["qc_manager"],
        "password_hash": pwd_context.hash("qc123456"),
        "avatar": "",
        "phone": "13800138001",
        "bio": "质控科主管，专注于医疗质量控制和病案审核工作。",
        "created_at": "2024-01-15T00:00:00Z",
        "last_login": None,
    },
    "doctor@medqc.com": {
        "id": "doctor-001",
        "email": "doctor@medqc.com",
        "display_name": "医务人员",
        "department": "内科",
        "roles": ["doctor"],
        "password_hash": pwd_context.hash("doctor123"),
        "avatar": "",
        "phone": "13800138002",
        "bio": "内科医生，从事临床诊疗和病案记录工作。",
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
            "patient_name": f"患者{i:02d}",
            "patient_age": 30 + (i % 50),
            "patient_gender": "male" if i % 2 == 0 else "female",
            "department": ["内科", "外科", "儿科", "妇科", "骨科"][i % 5],
            "admission_date": (datetime.utcnow()).strftime("%Y-%m-%d"),
            "record_type": ["inpatient", "outpatient", "emergency"][i % 3],
            "content": "示例病案记录",
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
        "name": "主诉完整性检查",
        "description": "检查病案中主诉部分是否完整，包含患者主要症状和持续时间",
        "category": "基本信息",
        "severity": "major",
        "weight": 10,
        "is_active": True,
        "conditions": "content.includes('主诉') && content.match(/\\d+[天日月年]/)",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T15:30:00Z",
        "execution_count": 1250,
        "pass_rate": 85.0,
        "issue_count": 187,
    },
    "rule-002": {
        "id": "rule-002",
        "rule_code": "QC002",
        "name": "诊断依据充分性",
        "description": "检查诊断是否有充分的依据支撑，包括症状、体征、检查结果等",
        "category": "诊断质量",
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
