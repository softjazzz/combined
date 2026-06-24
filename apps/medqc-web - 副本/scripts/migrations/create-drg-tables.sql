-- ========================================
-- DRG/DIP 系统数据库表创建脚本
-- ========================================
-- 执行说明：
-- 1. 在 Supabase Dashboard 的 SQL Editor 中执行此脚本
-- 2. 或者使用 TypeScript 迁移脚本自动执行
-- 3. 执行前请确保已创建 patients 和 admissions 表
-- ========================================

-- ========================================
-- 1. 病案首页主表 (case_front_page)
-- ========================================
CREATE TABLE IF NOT EXISTS case_front_page (
    front_page_id SERIAL PRIMARY KEY,
    admission_id VARCHAR(50) UNIQUE NOT NULL,
    patient_id VARCHAR(50) NOT NULL,

    -- 患者基本信息
    patient_name VARCHAR(100),
    patient_age INT,
    patient_gender CHAR(1) CHECK (patient_gender IN ('M', 'F')),
    admission_weight DECIMAL(5,2),  -- 新生儿体重（kg）

    -- 主诊断（编码员编码）
    primary_diagnosis_code VARCHAR(10) NOT NULL,
    primary_diagnosis_name VARCHAR(200) NOT NULL,

    -- 主要手术操作（编码员编码）
    main_procedure_code VARCHAR(10),
    main_procedure_name VARCHAR(200),
    main_procedure_date TIMESTAMP WITH TIME ZONE,

    -- 其他信息
    admission_route VARCHAR(50),  -- 入院途径（急诊/门诊/转院等）
    discharge_status VARCHAR(50),  -- 出院状态（治愈/好转/未愈/死亡等）
    total_hospital_days INT,
    total_cost DECIMAL(12,2),

    -- 编码工作追踪
    coder_id VARCHAR(50),  -- 编码员 ID
    coding_started_at TIMESTAMP WITH TIME ZONE,
    coding_completed_at TIMESTAMP WITH TIME ZONE,
    coding_status VARCHAR(20) DEFAULT 'draft' CHECK (coding_status IN ('draft', 'completed', 'reviewed')),

    -- 审核追踪
    reviewer_id VARCHAR(50),  -- 审核员 ID
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_status VARCHAR(20) DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),

    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP

    -- 外键约束（如果 admissions 表已存在）
    -- CONSTRAINT fk_admission FOREIGN KEY (admission_id) REFERENCES admissions(admission_id) ON DELETE CASCADE,
    -- CONSTRAINT fk_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_case_front_page_admission_id ON case_front_page(admission_id);
CREATE INDEX IF NOT EXISTS idx_case_front_page_coding_status ON case_front_page(coding_status);
CREATE INDEX IF NOT EXISTS idx_case_front_page_primary_diagnosis ON case_front_page(primary_diagnosis_code);
CREATE INDEX IF NOT EXISTS idx_case_front_page_coder_id ON case_front_page(coder_id);
CREATE INDEX IF NOT EXISTS idx_case_front_page_created_at ON case_front_page(created_at DESC);

-- 添加注释
COMMENT ON TABLE case_front_page IS '病案首页表：DRG分组的数据来源，包含编码员完成的诊断和手术操作编码';
COMMENT ON COLUMN case_front_page.primary_diagnosis_code IS '主诊断ICD-10编码';
COMMENT ON COLUMN case_front_page.main_procedure_code IS '主要手术操作ICD-9-CM-3编码';
COMMENT ON COLUMN case_front_page.coding_status IS '编码状态：draft=草稿, completed=已完成, reviewed=已审核';

-- ========================================
-- 2. 次诊断关联表 (case_front_page_diagnoses)
-- ========================================
CREATE TABLE IF NOT EXISTS case_front_page_diagnoses (
    id SERIAL PRIMARY KEY,
    front_page_id INT NOT NULL,
    diagnosis_code VARCHAR(10) NOT NULL,  -- ICD-10编码
    diagnosis_name VARCHAR(200) NOT NULL,
    sequence INT NOT NULL,  -- 次诊断顺序（1, 2, 3...）
    is_complication BOOLEAN DEFAULT FALSE,  -- 是否为并发症
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_front_page_diagnoses FOREIGN KEY (front_page_id)
        REFERENCES case_front_page(front_page_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cfp_diagnoses_front_page_id ON case_front_page_diagnoses(front_page_id);
CREATE INDEX IF NOT EXISTS idx_cfp_diagnoses_code ON case_front_page_diagnoses(diagnosis_code);

-- 添加注释
COMMENT ON TABLE case_front_page_diagnoses IS '病案首页次诊断列表';
COMMENT ON COLUMN case_front_page_diagnoses.is_complication IS '是否为并发症（影响DRG分组）';

-- ========================================
-- 3. 其他手术操作关联表 (case_front_page_procedures)
-- ========================================
CREATE TABLE IF NOT EXISTS case_front_page_procedures (
    id SERIAL PRIMARY KEY,
    front_page_id INT NOT NULL,
    procedure_code VARCHAR(10) NOT NULL,  -- ICD-9-CM-3编码
    procedure_name VARCHAR(200) NOT NULL,
    procedure_date TIMESTAMP WITH TIME ZONE,
    sequence INT NOT NULL,  -- 操作顺序（1, 2, 3...）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_front_page_procedures FOREIGN KEY (front_page_id)
        REFERENCES case_front_page(front_page_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cfp_procedures_front_page_id ON case_front_page_procedures(front_page_id);
CREATE INDEX IF NOT EXISTS idx_cfp_procedures_code ON case_front_page_procedures(procedure_code);

-- 添加注释
COMMENT ON TABLE case_front_page_procedures IS '病案首页其他手术操作列表';

-- ========================================
-- 4. DRG分组结果表 (drg_groupings)
-- ========================================
CREATE TABLE IF NOT EXISTS drg_groupings (
    grouping_id SERIAL PRIMARY KEY,
    admission_id VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,  -- 地区版本（sichuan/beijing/national等）

    -- 分组结果
    adrg_code VARCHAR(10) NOT NULL,
    adrg_name VARCHAR(200) NOT NULL,
    drg_code VARCHAR(10) NOT NULL,
    drg_name VARCHAR(200) NOT NULL,
    weight DECIMAL(6,4) NOT NULL,  -- 权重

    -- 支付相关
    baseline_payment DECIMAL(12,2) NOT NULL,  -- 基准支付金额
    actual_cost DECIMAL(12,2),  -- 实际费用
    profit_margin DECIMAL(12,2),  -- 盈亏（baseline_payment - actual_cost）

    -- 版本控制
    grouped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    version INT DEFAULT 1,  -- 分组版本号（支持重新分组）
    is_latest BOOLEAN DEFAULT TRUE,  -- 是否为最新版本

    -- 分组逻辑说明
    grouping_logic TEXT,  -- 分组规则说明

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP

    -- 外键约束
    -- CONSTRAINT fk_drg_admission FOREIGN KEY (admission_id) REFERENCES admissions(admission_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_drg_groupings_admission_id ON drg_groupings(admission_id);
CREATE INDEX IF NOT EXISTS idx_drg_groupings_is_latest ON drg_groupings(is_latest) WHERE is_latest = TRUE;
CREATE INDEX IF NOT EXISTS idx_drg_groupings_drg_code ON drg_groupings(drg_code);
CREATE INDEX IF NOT EXISTS idx_drg_groupings_grouped_at ON drg_groupings(grouped_at DESC);

-- 添加注释
COMMENT ON TABLE drg_groupings IS 'DRG分组结果表：记录每次分组的结果和版本历史';
COMMENT ON COLUMN drg_groupings.is_latest IS '是否为最新版本（编码变更时会产生新版本）';
COMMENT ON COLUMN drg_groupings.weight IS 'DRG权重系数';

-- ========================================
-- 5. 编码建议表 (coding_suggestions)
-- ========================================
CREATE TABLE IF NOT EXISTS coding_suggestions (
    suggestion_id SERIAL PRIMARY KEY,
    admission_id VARCHAR(50) NOT NULL,

    -- 建议类型
    suggestion_type VARCHAR(50) NOT NULL CHECK (suggestion_type IN (
        'missing_diagnosis',      -- 遗漏诊断
        'procedure_missing',      -- 遗漏手术操作
        'complication_marking',   -- 并发症标记建议
        'logic_conflict'          -- 逻辑冲突
    )),

    -- 建议内容
    diagnosis_code VARCHAR(10),
    diagnosis_name VARCHAR(200),
    message TEXT NOT NULL,  -- 建议描述
    evidence TEXT,  -- 病历依据
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error')),

    -- 处理状态
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    handled_at TIMESTAMP WITH TIME ZONE,
    handled_by VARCHAR(50)  -- 处理人（编码员/医生）

    -- 外键约束
    -- CONSTRAINT fk_suggestion_admission FOREIGN KEY (admission_id) REFERENCES admissions(admission_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_coding_suggestions_admission_id ON coding_suggestions(admission_id);
CREATE INDEX IF NOT EXISTS idx_coding_suggestions_status ON coding_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_coding_suggestions_created_at ON coding_suggestions(created_at DESC);

-- 添加注释
COMMENT ON TABLE coding_suggestions IS '编码优化建议表：LLM分析病历后给出的编码建议';
COMMENT ON COLUMN coding_suggestions.evidence IS '病历中的依据（引用原文）';

-- ========================================
-- 6. DRG预警表 (drg_alerts)
-- ========================================
CREATE TABLE IF NOT EXISTS drg_alerts (
    alert_id SERIAL PRIMARY KEY,
    admission_id VARCHAR(50) NOT NULL,

    -- 预警类型
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
        'cost_overrun',      -- 费用超标
        'los_long',          -- 住院日过长
        'coding_abnormal',   -- 编码异常
        'profit_loss'        -- 预计亏损
    )),

    -- 预警级别
    alert_level VARCHAR(20) DEFAULT 'info' CHECK (alert_level IN ('info', 'warning', 'critical')),

    -- 预警内容
    message TEXT NOT NULL,
    metric_value DECIMAL(12,2),  -- 指标值（如费用消耗率205%）
    threshold_value DECIMAL(12,2),  -- 阈值（如100%）

    -- 处理状态
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    handled_by VARCHAR(50),
    handled_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'acknowledged', 'resolved'))

    -- 外键约束
    -- CONSTRAINT fk_alert_admission FOREIGN KEY (admission_id) REFERENCES admissions(admission_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_drg_alerts_admission_id ON drg_alerts(admission_id);
CREATE INDEX IF NOT EXISTS idx_drg_alerts_status ON drg_alerts(status);
CREATE INDEX IF NOT EXISTS idx_drg_alerts_alert_level ON drg_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_drg_alerts_triggered_at ON drg_alerts(triggered_at DESC);

-- 添加注释
COMMENT ON TABLE drg_alerts IS 'DRG预警表：实时监控产生的费用、住院日等预警信息';

-- ========================================
-- 7. ICD编码库表 (icd10_codes)
-- ========================================
CREATE TABLE IF NOT EXISTS icd10_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),  -- 章节分类
    notes TEXT,  -- 编码说明
    includes TEXT[],  -- 包含项（数组）
    excludes TEXT[],  -- 排除项（数组）
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引（支持全文检索）
CREATE INDEX IF NOT EXISTS idx_icd10_code ON icd10_codes(code);
CREATE INDEX IF NOT EXISTS idx_icd10_name ON icd10_codes USING GIN (to_tsvector('chinese', name));
CREATE INDEX IF NOT EXISTS idx_icd10_category ON icd10_codes(category);

-- 添加注释
COMMENT ON TABLE icd10_codes IS 'ICD-10诊断编码库';

-- ========================================
-- 8. ICD-9-CM-3手术操作编码库表 (icd9_procedures)
-- ========================================
CREATE TABLE IF NOT EXISTS icd9_procedures (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),  -- 章节分类
    notes TEXT,  -- 编码说明
    includes TEXT[],
    excludes TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_icd9_code ON icd9_procedures(code);
CREATE INDEX IF NOT EXISTS idx_icd9_name ON icd9_procedures USING GIN (to_tsvector('chinese', name));
CREATE INDEX IF NOT EXISTS idx_icd9_category ON icd9_procedures(category);

-- 添加注释
COMMENT ON TABLE icd9_procedures IS 'ICD-9-CM-3手术操作编码库';

-- ========================================
-- 9. 触发器：自动更新 updated_at
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 case_front_page 表添加触发器
DROP TRIGGER IF EXISTS update_case_front_page_updated_at ON case_front_page;
CREATE TRIGGER update_case_front_page_updated_at
    BEFORE UPDATE ON case_front_page
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 10. 触发器：病案首页变更时自动重新分组（可选）
-- ========================================
-- 注：实际应该通过应用层触发，这里仅作示例
-- CREATE OR REPLACE FUNCTION trigger_drg_regrouping()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     -- 将旧版本标记为非最新
--     UPDATE drg_groupings
--     SET is_latest = FALSE
--     WHERE admission_id = NEW.admission_id AND is_latest = TRUE;
--
--     -- 这里应该调用 OpenDRG 重新分组（由应用层处理）
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- ========================================
-- 完成提示
-- ========================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'DRG表创建完成！';
    RAISE NOTICE '已创建的表：';
    RAISE NOTICE '  1. case_front_page（病案首页）';
    RAISE NOTICE '  2. case_front_page_diagnoses（次诊断）';
    RAISE NOTICE '  3. case_front_page_procedures（手术操作）';
    RAISE NOTICE '  4. drg_groupings（DRG分组结果）';
    RAISE NOTICE '  5. coding_suggestions（编码建议）';
    RAISE NOTICE '  6. drg_alerts（预警信息）';
    RAISE NOTICE '  7. icd10_codes（ICD-10编码库）';
    RAISE NOTICE '  8. icd9_procedures（ICD-9-CM-3编码库）';
    RAISE NOTICE '========================================';
END $$;
