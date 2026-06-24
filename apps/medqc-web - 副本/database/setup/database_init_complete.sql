-- =============================================
-- 医疗质控系统数据库完整初始化脚本
-- 版本: 2.0.0 (全新设计)
-- 创建时间: 2024-12-25
-- 新 Supabase 项目: https://dgsdkdbjpucyawnyfbdu.supabase.co
-- =============================================

-- 第一步：启用必要的 PostgreSQL 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 设置时区
SET timezone = 'Asia/Shanghai';

-- =============================================
-- 第二步：用户管理相关表
-- =============================================

-- 1. 用户档案表
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    avatar_url TEXT,
    department_id UUID,
    role_type VARCHAR(20) NOT NULL DEFAULT 'doctor' 
        CHECK (role_type IN ('admin', 'doctor', 'nurse', 'qc_manager', 'viewer')),
    job_title VARCHAR(100),
    license_number VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_id UNIQUE (user_id)
);

-- 2. 科室管理表
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50) NOT NULL DEFAULT 'clinical'
        CHECK (category IN ('clinical', 'surgical', 'emergency', 'pediatric', 'obstetrics', 'icu', 'diagnostic')),
    parent_id UUID REFERENCES departments(id),
    director_id UUID,
    contact_phone VARCHAR(20),
    location VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 添加科室外键约束
ALTER TABLE user_profiles 
ADD CONSTRAINT fk_user_department 
FOREIGN KEY (department_id) REFERENCES departments(id);

ALTER TABLE departments 
ADD CONSTRAINT fk_department_director 
FOREIGN KEY (director_id) REFERENCES user_profiles(id);

-- =============================================
-- 第三步：业务核心表
-- =============================================

-- 3. 医疗记录表
CREATE TABLE medical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_number VARCHAR(50) UNIQUE NOT NULL,
    patient_name VARCHAR(100) NOT NULL,
    patient_id VARCHAR(50),
    patient_age INTEGER CHECK (patient_age >= 0 AND patient_age <= 150),
    patient_gender VARCHAR(10) CHECK (patient_gender IN ('男', '女', '未知')),
    department_id UUID NOT NULL REFERENCES departments(id),
    doctor_id UUID REFERENCES user_profiles(id),
    admission_date DATE,
    discharge_date DATE,
    record_type VARCHAR(20) NOT NULL DEFAULT 'inpatient'
        CHECK (record_type IN ('inpatient', 'outpatient', 'emergency')),
    diagnosis_primary TEXT,
    diagnosis_secondary TEXT[],
    content TEXT NOT NULL,
    content_sections JSONB DEFAULT '{}',
    file_attachments JSONB DEFAULT '[]',
    total_pages INTEGER DEFAULT 1,
    word_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'analyzing', 'completed', 'failed', 'archived')),
    qc_score DECIMAL(5,2),
    qc_grade VARCHAR(5) CHECK (qc_grade IN ('甲级', '乙级', '丙级')),
    priority_level INTEGER DEFAULT 1 CHECK (priority_level BETWEEN 1 AND 5),
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    created_by UUID NOT NULL REFERENCES user_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_dates CHECK (discharge_date IS NULL OR discharge_date >= admission_date)
);

-- 4. 质控规则表
CREATE TABLE qc_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL
        CHECK (category IN ('completeness', 'accuracy', 'timeliness', 'consistency', 'compliance')),
    subcategory VARCHAR(100),
    rule_type VARCHAR(20) DEFAULT 'semantic'
        CHECK (rule_type IN ('logical', 'semantic', 'hybrid')),
    severity VARCHAR(20) DEFAULT 'minor'
        CHECK (severity IN ('critical', 'major', 'minor')),
    applicable_record_types TEXT[] DEFAULT ARRAY['inpatient', 'outpatient', 'emergency'],
    applicable_departments UUID[],
    target_sections TEXT[],
    check_logic JSONB NOT NULL DEFAULT '{}',
    scoring_config JSONB DEFAULT '{
        "default_deduction": 0,
        "max_deduction": 10,
        "weight_factor": 1.0
    }',
    prompt_template TEXT,
    examples JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    execution_order INTEGER DEFAULT 0,
    estimated_tokens INTEGER DEFAULT 100,
    timeout_seconds INTEGER DEFAULT 30,
    version VARCHAR(10) DEFAULT '1.0',
    created_by UUID NOT NULL REFERENCES user_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 质控结果表
CREATE TABLE qc_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES qc_rules(id),
    analysis_batch_id UUID,
    result_status VARCHAR(20) NOT NULL
        CHECK (result_status IN ('passed', 'failed', 'warning', 'error')),
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    deduction_score DECIMAL(5,2) DEFAULT 0,
    issue_description TEXT,
    evidence_text TEXT,
    evidence_location JSONB,
    suggestions TEXT[],
    ai_reasoning TEXT,
    manual_review_status VARCHAR(20) DEFAULT 'pending'
        CHECK (manual_review_status IN ('pending', 'confirmed', 'disputed', 'corrected')),
    manual_reviewer_id UUID REFERENCES user_profiles(id),
    manual_review_notes TEXT,
    processing_time_ms INTEGER,
    tokens_used INTEGER,
    model_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT unique_record_rule UNIQUE (record_id, rule_id, analysis_batch_id)
);

-- 6. 质控分析缓存表
CREATE TABLE qc_analysis_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    rule_id UUID NOT NULL REFERENCES qc_rules(id),
    cached_result JSONB NOT NULL,
    hit_count INTEGER DEFAULT 1,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- 第四步：任务处理相关表
-- =============================================

-- 7. 批量处理任务表
CREATE TABLE batch_processing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(200) NOT NULL,
    task_type VARCHAR(50) NOT NULL
        CHECK (task_type IN ('upload', 'analysis', 'export', 'cleanup')),
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    total_items INTEGER NOT NULL DEFAULT 0 CHECK (total_items >= 0),
    processed_items INTEGER DEFAULT 0 CHECK (processed_items >= 0),
    failed_items INTEGER DEFAULT 0 CHECK (failed_items >= 0),
    success_items INTEGER DEFAULT 0 CHECK (success_items >= 0),
    progress_percentage DECIMAL(5,2) DEFAULT 0 
        CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    estimated_duration_minutes INTEGER,
    actual_duration_minutes INTEGER,
    error_details JSONB DEFAULT '[]',
    task_config JSONB DEFAULT '{}',
    result_summary JSONB,
    created_by UUID NOT NULL REFERENCES user_profiles(id),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_item_counts CHECK (
        processed_items = success_items + failed_items AND
        processed_items <= total_items
    )
);

-- 8. 质控分析历史表
CREATE TABLE qc_analysis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id),
    analysis_batch_id UUID NOT NULL,
    total_rules_checked INTEGER NOT NULL,
    rules_passed INTEGER DEFAULT 0,
    rules_failed INTEGER DEFAULT 0,
    rules_warning INTEGER DEFAULT 0,
    overall_score DECIMAL(5,2),
    grade VARCHAR(5),
    total_deduction DECIMAL(5,2) DEFAULT 0,
    processing_time_ms INTEGER,
    total_tokens_used INTEGER,
    cost_estimate DECIMAL(8,4),
    analysis_config JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}',
    created_by UUID NOT NULL REFERENCES user_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_rule_counts CHECK (
        rules_passed + rules_failed + rules_warning = total_rules_checked
    )
);

-- 9. 告警记录表
CREATE TABLE alert_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL
        CHECK (alert_type IN ('critical_issue', 'system_error', 'performance_warning', 'compliance_violation')),
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    related_record_id UUID REFERENCES medical_records(id),
    related_rule_id UUID REFERENCES qc_rules(id),
    related_user_id UUID REFERENCES user_profiles(id),
    status VARCHAR(20) DEFAULT 'active'
        CHECK (status IN ('active', 'acknowledged', 'resolved', 'dismissed')),
    auto_resolve BOOLEAN DEFAULT false,
    resolved_by UUID REFERENCES user_profiles(id),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
