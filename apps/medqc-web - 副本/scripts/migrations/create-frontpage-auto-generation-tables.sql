-- =====================================================
-- 病案首页自动生成功能 - 数据库迁移脚本
-- 版本: v1.0
-- 创建日期: 2025-01-19
-- 描述: 创建病案首页自动生成所需的新表和扩展现有表
-- =====================================================

-- =====================================================
-- 1. 病案首页自动生成任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS frontpage_generation_tasks (
    -- 主键
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联信息
    admission_id VARCHAR(50) NOT NULL,
    patient_id VARCHAR(50) NOT NULL,
    
    -- 任务状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'reviewing')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    
    -- 进度追踪
    current_step INT DEFAULT 1 CHECK (current_step >= 1 AND current_step <= 7),
    total_steps INT DEFAULT 7,
    progress_percentage INT DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    
    -- 分步提取结果（JSONB存储）
    extraction_results JSONB DEFAULT '{}'::jsonb,
    
    -- 生成结果ID（关联到 case_front_page）
    generated_front_page_id INT,
    
    -- 操作人
    created_by VARCHAR(50) NOT NULL,
    reviewed_by VARCHAR(50),
    
    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_fg_tasks_admission_id ON frontpage_generation_tasks(admission_id);
CREATE INDEX IF NOT EXISTS idx_fg_tasks_patient_id ON frontpage_generation_tasks(patient_id);
CREATE INDEX IF NOT EXISTS idx_fg_tasks_status ON frontpage_generation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_fg_tasks_created_at ON frontpage_generation_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fg_tasks_created_by ON frontpage_generation_tasks(created_by);

-- GIN索引用于JSONB全文检索
CREATE INDEX IF NOT EXISTS idx_fg_tasks_extraction_results ON frontpage_generation_tasks USING GIN (extraction_results);

-- 注释
COMMENT ON TABLE frontpage_generation_tasks IS '病案首页自动生成任务表：跟踪LLM提取的完整流程和分步结果';
COMMENT ON COLUMN frontpage_generation_tasks.task_id IS '任务唯一标识符';
COMMENT ON COLUMN frontpage_generation_tasks.status IS '任务状态：pending-待处理, processing-处理中, completed-已完成, failed-失败, reviewing-审核中';
COMMENT ON COLUMN frontpage_generation_tasks.current_step IS '当前执行步骤：1-基本信息, 2-住院信息, 3-诊断, 4-入院病情, 5-ICD-10编码, 6-手术, 7-ICD-9编码';
COMMENT ON COLUMN frontpage_generation_tasks.extraction_results IS '分步提取结果JSON：{basic_info, hospitalization, diagnosis, procedures, other_medical, staff, costs}';

-- =====================================================
-- 2. AI建议表
-- =====================================================
CREATE TABLE IF NOT EXISTS ai_suggestions (
    -- 主键
    suggestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联任务
    task_id UUID NOT NULL,
    admission_id VARCHAR(50) NOT NULL,
    
    -- 建议类型
    suggestion_type VARCHAR(50) NOT NULL CHECK (suggestion_type IN (
        'missing_field',        -- 字段缺失
        'data_conflict',        -- 数据冲突
        'alternative_value',    -- 建议值
        'coding_suggestion',    -- 编码建议
        'logic_warning'         -- 逻辑警告
    )),
    
    -- 字段路径和值
    field_path VARCHAR(200),            -- 如 "basic_info.birth_date"
    current_value TEXT,                 -- 当前值
    suggested_value TEXT,               -- 建议值
    
    -- 建议内容
    message TEXT NOT NULL,
    evidence TEXT,                      -- 病历依据（引用原文）
    confidence DECIMAL(4, 3) CHECK (confidence >= 0 AND confidence <= 1),
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error')),
    
    -- 处理状态
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'ignored')),
    handled_at TIMESTAMP WITH TIME ZONE,
    handled_by VARCHAR(50),
    handle_comment TEXT,                -- 处理备注
    
    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_ai_sugg_task_id ON ai_suggestions(task_id);
CREATE INDEX IF NOT EXISTS idx_ai_sugg_admission_id ON ai_suggestions(admission_id);
CREATE INDEX IF NOT EXISTS idx_ai_sugg_status ON ai_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_ai_sugg_severity ON ai_suggestions(severity);
CREATE INDEX IF NOT EXISTS idx_ai_sugg_type ON ai_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_ai_sugg_created_at ON ai_suggestions(created_at DESC);

-- 外键约束
ALTER TABLE ai_suggestions
    ADD CONSTRAINT fk_ai_sugg_task 
    FOREIGN KEY (task_id) 
    REFERENCES frontpage_generation_tasks(task_id) 
    ON DELETE CASCADE;

-- 注释
COMMENT ON TABLE ai_suggestions IS 'AI建议表：LLM生成的字段建议、警告和冲突检测';
COMMENT ON COLUMN ai_suggestions.suggestion_type IS '建议类型：missing_field-缺失, data_conflict-冲突, alternative_value-建议值, coding_suggestion-编码建议, logic_warning-逻辑警告';
COMMENT ON COLUMN ai_suggestions.field_path IS '字段路径，用于前端定位（如 basic_info.birth_date）';
COMMENT ON COLUMN ai_suggestions.evidence IS '病历文本依据，用于证明建议的合理性';

-- =====================================================
-- 3. ICD编码候选表
-- =====================================================
CREATE TABLE IF NOT EXISTS icd_candidates (
    -- 主键
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联任务
    task_id UUID NOT NULL,
    admission_id VARCHAR(50) NOT NULL,
    
    -- 编码类型
    code_type VARCHAR(10) NOT NULL CHECK (code_type IN ('ICD10', 'ICD9')),
    
    -- 原始文本
    original_text TEXT NOT NULL,        -- 原始诊断/手术名称
    original_type VARCHAR(50),          -- 类型：main_diagnosis | other_diagnosis | main_procedure | other_procedure
    sequence INT,                       -- 在列表中的顺序
    
    -- 候选编码
    code VARCHAR(10) NOT NULL,
    code_name VARCHAR(200) NOT NULL,
    confidence DECIMAL(4, 3) CHECK (confidence >= 0 AND confidence <= 1),
    reasoning TEXT,                     -- 推荐理由
    source VARCHAR(50) CHECK (source IN (
        'exact_match',                  -- 精确匹配
        'semantic_match',               -- 语义匹配
        'knowledge_graph',              -- 知识图谱
        'llm_inference'                 -- LLM推理
    )),
    
    -- 候选排名
    rank INT CHECK (rank >= 1 AND rank <= 3),  -- Top 3排名
    
    -- 选中状态
    is_selected BOOLEAN DEFAULT FALSE,
    selected_by VARCHAR(50),
    selected_at TIMESTAMP WITH TIME ZONE,
    selection_comment TEXT,
    
    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_icd_cand_task_id ON icd_candidates(task_id);
CREATE INDEX IF NOT EXISTS idx_icd_cand_admission_id ON icd_candidates(admission_id);
CREATE INDEX IF NOT EXISTS idx_icd_cand_code ON icd_candidates(code);
CREATE INDEX IF NOT EXISTS idx_icd_cand_code_type ON icd_candidates(code_type);
CREATE INDEX IF NOT EXISTS idx_icd_cand_is_selected ON icd_candidates(is_selected);
CREATE INDEX IF NOT EXISTS idx_icd_cand_confidence ON icd_candidates(confidence DESC);

-- 外键约束
ALTER TABLE icd_candidates
    ADD CONSTRAINT fk_icd_cand_task 
    FOREIGN KEY (task_id) 
    REFERENCES frontpage_generation_tasks(task_id) 
    ON DELETE CASCADE;

-- 注释
COMMENT ON TABLE icd_candidates IS 'ICD编码候选表：存储LLM推荐的Top 3编码候选及选择状态';
COMMENT ON COLUMN icd_candidates.code_type IS '编码类型：ICD10-诊断编码, ICD9-手术操作编码';
COMMENT ON COLUMN icd_candidates.source IS '推荐来源：exact_match-精确匹配, semantic_match-语义匹配, knowledge_graph-知识图谱, llm_inference-LLM推理';
COMMENT ON COLUMN icd_candidates.rank IS 'Top 3排名：1-第一推荐, 2-第二推荐, 3-第三推荐';

-- =====================================================
-- 4. 扩展现有的 case_front_page 表
-- =====================================================

-- 4.1 添加患者基本信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS patient_name VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS gender CHAR(1) CHECK (gender IN ('1', '2', '9'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS age_years INT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS age_months INT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS age_days INT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS nationality VARCHAR(50) DEFAULT '中国';
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS ethnicity VARCHAR(50);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS marital_status CHAR(1) CHECK (marital_status IN ('1', '2', '3', '4', '9'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS id_number VARCHAR(18);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS current_address TEXT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS contact_name VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS contact_relation VARCHAR(50);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(20);

-- 4.2 添加住院信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS hospital_name VARCHAR(200);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS hospital_code VARCHAR(50);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS medical_record_no VARCHAR(50);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS admission_times_in_hospital INT DEFAULT 1;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS admission_way VARCHAR(20);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS admission_datetime TIMESTAMP WITH TIME ZONE;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS discharge_datetime TIMESTAMP WITH TIME ZONE;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS admission_dept VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS discharge_dept VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS actual_hospital_days INT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS discharge_status VARCHAR(20);

-- 4.3 添加诊断信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS primary_diagnosis_code VARCHAR(10);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS primary_diagnosis_name VARCHAR(200);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS admission_condition CHAR(1) CHECK (admission_condition IN ('1', '2', '3', '4'));

-- 4.4 添加手术信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS main_procedure_code VARCHAR(10);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS main_procedure_name VARCHAR(200);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS main_procedure_date DATE;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS main_procedure_level CHAR(1) CHECK (main_procedure_level IN ('1', '2', '3', '4'));

-- 4.5 添加其他医疗信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS drug_allergy_flag CHAR(1) CHECK (drug_allergy_flag IN ('1', '2', '9'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS drug_allergy_list TEXT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS abo_blood_type VARCHAR(10);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS rh_blood_type CHAR(1) CHECK (rh_blood_type IN ('1', '2', '9'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS ventilation_hours DECIMAL(10, 2);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS icu_stay_hours DECIMAL(10, 2);

-- 4.6 添加医护人员字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS dept_director VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS chief_physician VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS attending_physician VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS resident_physician VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS responsible_nurse VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS qc_physician VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS qc_nurse VARCHAR(100);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS qc_date DATE;

-- 4.7 添加费用信息字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS total_cost DECIMAL(12, 2);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS self_paid DECIMAL(12, 2);

-- 4.8 添加JSONB字段存储完整结构化数据
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS basic_info JSONB;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS hospitalization JSONB;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS diagnosis_procedures JSONB;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS other_medical_info JSONB;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS staff JSONB;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS costs JSONB;

-- 4.9 添加审核和编码追踪字段
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS coding_status VARCHAR(20) DEFAULT 'draft' 
    CHECK (coding_status IN ('draft', 'completed', 'reviewed'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'pending'
    CHECK (review_status IN ('pending', 'approved', 'rejected'));
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS review_comments TEXT;
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS reviewer_id VARCHAR(50);
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE;

-- 4.10 添加关联字段（反向引用生成任务）
ALTER TABLE case_front_page ADD COLUMN IF NOT EXISTS generation_task_id UUID;

-- 4.11 创建索引
CREATE INDEX IF NOT EXISTS idx_case_fp_patient_name ON case_front_page(patient_name);
CREATE INDEX IF NOT EXISTS idx_case_fp_admission_date ON case_front_page(admission_datetime);
CREATE INDEX IF NOT EXISTS idx_case_fp_discharge_date ON case_front_page(discharge_datetime);
CREATE INDEX IF NOT EXISTS idx_case_fp_primary_diag_code ON case_front_page(primary_diagnosis_code);
CREATE INDEX IF NOT EXISTS idx_case_fp_coding_status ON case_front_page(coding_status);
CREATE INDEX IF NOT EXISTS idx_case_fp_review_status ON case_front_page(review_status);

-- GIN索引用于JSONB字段
CREATE INDEX IF NOT EXISTS idx_case_fp_basic_info ON case_front_page USING GIN (basic_info);
CREATE INDEX IF NOT EXISTS idx_case_fp_hospitalization ON case_front_page USING GIN (hospitalization);
CREATE INDEX IF NOT EXISTS idx_case_fp_diagnosis_procedures ON case_front_page USING GIN (diagnosis_procedures);

-- 注释
COMMENT ON COLUMN case_front_page.basic_info IS '患者基本信息完整JSON数据';
COMMENT ON COLUMN case_front_page.hospitalization IS '住院信息完整JSON数据';
COMMENT ON COLUMN case_front_page.diagnosis_procedures IS '诊断和手术完整JSON数据';
COMMENT ON COLUMN case_front_page.admission_condition IS '入院病情：1-有, 2-临床未确定, 3-情况不明, 4-无';
COMMENT ON COLUMN case_front_page.coding_status IS '编码状态：draft-草稿, completed-已完成, reviewed-已审核';
COMMENT ON COLUMN case_front_page.review_status IS '审核状态：pending-待审核, approved-已通过, rejected-已拒绝';

-- =====================================================
-- 5. 扩展现有的 case_front_page_diagnoses 表
-- =====================================================
ALTER TABLE case_front_page_diagnoses ADD COLUMN IF NOT EXISTS admission_condition CHAR(1) 
    CHECK (admission_condition IN ('1', '2', '3', '4'));
ALTER TABLE case_front_page_diagnoses ADD COLUMN IF NOT EXISTS admission_condition_reasoning TEXT;
ALTER TABLE case_front_page_diagnoses ADD COLUMN IF NOT EXISTS icd_candidates JSONB;
ALTER TABLE case_front_page_diagnoses ADD COLUMN IF NOT EXISTS confidence DECIMAL(4, 3);
ALTER TABLE case_front_page_diagnoses ADD COLUMN IF NOT EXISTS extracted_from TEXT; -- 提取来源（病历章节）

-- 索引
CREATE INDEX IF NOT EXISTS idx_fp_diag_admission_cond ON case_front_page_diagnoses(admission_condition);
CREATE INDEX IF NOT EXISTS idx_fp_diag_icd_candidates ON case_front_page_diagnoses USING GIN (icd_candidates);

-- 注释
COMMENT ON COLUMN case_front_page_diagnoses.admission_condition IS '入院病情：1-有, 2-临床未确定, 3-情况不明, 4-无';
COMMENT ON COLUMN case_front_page_diagnoses.admission_condition_reasoning IS 'LLM推理入院病情的依据';
COMMENT ON COLUMN case_front_page_diagnoses.icd_candidates IS 'ICD-10编码候选JSON数组（Top 3）';

-- =====================================================
-- 6. 扩展现有的 case_front_page_procedures 表
-- =====================================================
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS icd_candidates JSONB;
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS level CHAR(1) CHECK (level IN ('1', '2', '3', '4'));
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS surgeon_name VARCHAR(100);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS surgeon_code VARCHAR(50);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS assistant1_name VARCHAR(100);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS assistant2_name VARCHAR(100);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS anesthetist_name VARCHAR(100);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS anesthesia_method VARCHAR(100);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS incision_healing_grade VARCHAR(10);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS confidence DECIMAL(4, 3);
ALTER TABLE case_front_page_procedures ADD COLUMN IF NOT EXISTS extracted_from TEXT;

-- 索引
CREATE INDEX IF NOT EXISTS idx_fp_proc_icd_candidates ON case_front_page_procedures USING GIN (icd_candidates);
CREATE INDEX IF NOT EXISTS idx_fp_proc_level ON case_front_page_procedures(level);

-- 注释
COMMENT ON COLUMN case_front_page_procedures.icd_candidates IS 'ICD-9-CM-3编码候选JSON数组（Top 3）';
COMMENT ON COLUMN case_front_page_procedures.level IS '手术级别：1-四级, 2-三级, 3-二级, 4-一级';

-- =====================================================
-- 7. 添加外键约束
-- =====================================================
ALTER TABLE case_front_page 
    ADD CONSTRAINT fk_case_fp_generation_task 
    FOREIGN KEY (generation_task_id) 
    REFERENCES frontpage_generation_tasks(task_id) 
    ON DELETE SET NULL;

ALTER TABLE frontpage_generation_tasks
    ADD CONSTRAINT fk_fg_task_case_fp
    FOREIGN KEY (generated_front_page_id)
    REFERENCES case_front_page(front_page_id)
    ON DELETE SET NULL;

-- =====================================================
-- 8. 创建触发器：自动更新 updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 frontpage_generation_tasks 表创建触发器
DROP TRIGGER IF EXISTS trigger_update_fg_tasks_updated_at ON frontpage_generation_tasks;
CREATE TRIGGER trigger_update_fg_tasks_updated_at
    BEFORE UPDATE ON frontpage_generation_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 9. 创建视图：病案首页完整信息
-- =====================================================
CREATE OR REPLACE VIEW v_case_front_page_complete AS
SELECT 
    cfp.front_page_id,
    cfp.admission_id,
    cfp.patient_id,
    
    -- 基本信息
    cfp.patient_name,
    cfp.gender,
    cfp.birth_date,
    cfp.age_years,
    cfp.id_number,
    cfp.contact_name,
    cfp.contact_phone,
    
    -- 住院信息
    cfp.medical_record_no,
    cfp.admission_datetime,
    cfp.discharge_datetime,
    cfp.actual_hospital_days,
    cfp.admission_dept,
    cfp.discharge_dept,
    
    -- 主要诊断
    cfp.primary_diagnosis_code,
    cfp.primary_diagnosis_name,
    cfp.admission_condition,
    
    -- 主要手术
    cfp.main_procedure_code,
    cfp.main_procedure_name,
    cfp.main_procedure_date,
    
    -- 费用
    cfp.total_cost,
    cfp.self_paid,
    
    -- 状态
    cfp.coding_status,
    cfp.review_status,
    
    -- 关联任务信息
    fgt.task_id,
    fgt.status as task_status,
    fgt.progress_percentage,
    fgt.started_at as generation_started_at,
    fgt.completed_at as generation_completed_at,
    
    -- JSONB完整数据
    cfp.basic_info,
    cfp.hospitalization,
    cfp.diagnosis_procedures,
    cfp.other_medical_info,
    cfp.staff,
    cfp.costs,
    
    -- 审计信息
    cfp.created_at,
    cfp.updated_at
FROM case_front_page cfp
LEFT JOIN frontpage_generation_tasks fgt ON cfp.generation_task_id = fgt.task_id;

COMMENT ON VIEW v_case_front_page_complete IS '病案首页完整信息视图：整合case_front_page和生成任务信息';

-- =====================================================
-- 10. 创建统计视图：任务执行统计
-- =====================================================
CREATE OR REPLACE VIEW v_generation_task_stats AS
SELECT 
    DATE(created_at) as date,
    status,
    COUNT(*) as task_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds,
    AVG(progress_percentage) as avg_progress,
    COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as error_count
FROM frontpage_generation_tasks
GROUP BY DATE(created_at), status
ORDER BY date DESC, status;

COMMENT ON VIEW v_generation_task_stats IS '生成任务统计视图：按日期和状态统计任务执行情况';

-- =====================================================
-- 11. 插入测试数据（可选）
-- =====================================================
-- 注意：生产环境中请注释掉此部分

-- 示例：插入一个测试生成任务
-- INSERT INTO frontpage_generation_tasks (
--     admission_id, 
--     patient_id, 
--     status, 
--     created_by
-- ) VALUES (
--     'demo_admission_001',
--     'demo_patient_001',
--     'pending',
--     'system'
-- );

-- =====================================================
-- 12. 授权（根据实际情况调整）
-- =====================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON frontpage_generation_tasks TO medqc_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ai_suggestions TO medqc_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON icd_candidates TO medqc_app_user;
-- GRANT SELECT ON v_case_front_page_complete TO medqc_app_user;
-- GRANT SELECT ON v_generation_task_stats TO medqc_app_user;

-- =====================================================
-- 迁移完成
-- =====================================================
SELECT 'Migration completed successfully!' as status;
