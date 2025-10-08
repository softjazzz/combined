-- =====================================================
-- 性能优化索引迁移
-- 版本: 006
-- 日期: 2025-10-08
-- 目的: 添加数据库索引以提升查询性能
-- =====================================================

-- =====================================================
-- 1. medical_records 表索引
-- =====================================================

-- 患者姓名索引（从 patient_info JSONB 中提取）
CREATE INDEX IF NOT EXISTS idx_medical_records_patient_name 
ON medical_records ((patient_info->>'name'));

-- 病案号索引（已有 UNIQUE 约束，自动创建索引，这里确保存在）
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_medical_records_record_number 
-- ON medical_records (record_number);

-- 科室索引（常用于筛选）
CREATE INDEX IF NOT EXISTS idx_medical_records_department 
ON medical_records (department);

-- 状态索引（常用于筛选）
CREATE INDEX IF NOT EXISTS idx_medical_records_status 
ON medical_records (status);

-- 创建时间索引（常用于排序和时间范围查询）
CREATE INDEX IF NOT EXISTS idx_medical_records_created_at 
ON medical_records (created_at DESC);

-- 更新时间索引
CREATE INDEX IF NOT EXISTS idx_medical_records_updated_at 
ON medical_records (updated_at DESC);

-- 导入方法索引
CREATE INDEX IF NOT EXISTS idx_medical_records_import_method 
ON medical_records (import_method);

-- 复合索引：状态 + 创建时间（常用组合查询）
CREATE INDEX IF NOT EXISTS idx_medical_records_status_created 
ON medical_records (status, created_at DESC);

-- 复合索引：科室 + 状态（常用组合查询）
CREATE INDEX IF NOT EXISTS idx_medical_records_dept_status 
ON medical_records (department, status);

-- AI 提供商索引（用于统计分析）
CREATE INDEX IF NOT EXISTS idx_medical_records_ai_provider 
ON medical_records (ai_provider);

-- =====================================================
-- 2. medical_documents 表索引
-- =====================================================

-- 病案ID索引（外键，常用于关联查询）
CREATE INDEX IF NOT EXISTS idx_medical_documents_record_id 
ON medical_documents (record_id);

-- 文书类型索引（常用于筛选）
CREATE INDEX IF NOT EXISTS idx_medical_documents_type 
ON medical_documents (document_type);

-- 状态索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_status 
ON medical_documents (status);

-- 创建时间索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_created_at 
ON medical_documents (created_at DESC);

-- 排序字段索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_sort_order 
ON medical_documents (sort_order);

-- 复合索引：病案ID + 文书类型（常用组合查询）
CREATE INDEX IF NOT EXISTS idx_medical_documents_record_type 
ON medical_documents (record_id, document_type);

-- 复合索引：病案ID + 排序（用于获取病案的所有文书并排序）
CREATE INDEX IF NOT EXISTS idx_medical_documents_record_sort 
ON medical_documents (record_id, sort_order);

-- AI 分类标记索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_ai_classified 
ON medical_documents (ai_classified);

-- =====================================================
-- 3. qc_results 表索引（如果存在）
-- =====================================================

-- 检查表是否存在
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'qc_results') THEN
        -- 病案ID索引
        CREATE INDEX IF NOT EXISTS idx_qc_results_record_id 
        ON qc_results (record_id);
        
        -- 规则ID索引
        CREATE INDEX IF NOT EXISTS idx_qc_results_rule_id 
        ON qc_results (rule_id);
        
        -- 检查结果索引
        CREATE INDEX IF NOT EXISTS idx_qc_results_check_result 
        ON qc_results (check_result);
        
        -- 创建时间索引
        CREATE INDEX IF NOT EXISTS idx_qc_results_created_at 
        ON qc_results (created_at DESC);
        
        -- 复合索引：病案ID + 检查结果
        CREATE INDEX IF NOT EXISTS idx_qc_results_record_result 
        ON qc_results (record_id, check_result);
        
        -- 复合索引：规则ID + 检查结果（用于统计规则通过率）
        CREATE INDEX IF NOT EXISTS idx_qc_results_rule_result 
        ON qc_results (rule_id, check_result);
    END IF;
END $$;

-- =====================================================
-- 4. qc_rules 表索引（如果存在）
-- =====================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'qc_rules') THEN
        -- 规则代码索引
        CREATE INDEX IF NOT EXISTS idx_qc_rules_rule_code 
        ON qc_rules (rule_code);
        
        -- 规则类别索引
        CREATE INDEX IF NOT EXISTS idx_qc_rules_category 
        ON qc_rules (category);
        
        -- 启用状态索引
        CREATE INDEX IF NOT EXISTS idx_qc_rules_is_enabled 
        ON qc_rules (is_enabled);
        
        -- 复合索引：类别 + 启用状态
        CREATE INDEX IF NOT EXISTS idx_qc_rules_category_enabled 
        ON qc_rules (category, is_enabled);
    END IF;
END $$;

-- =====================================================
-- 5. LLM 配置表索引
-- =====================================================

-- llm_api_providers 表
CREATE INDEX IF NOT EXISTS idx_llm_providers_code 
ON llm_api_providers (provider_code);

CREATE INDEX IF NOT EXISTS idx_llm_providers_active 
ON llm_api_providers (is_active);

CREATE INDEX IF NOT EXISTS idx_llm_providers_sort 
ON llm_api_providers (sort_order);

-- llm_models 表
CREATE INDEX IF NOT EXISTS idx_llm_models_provider 
ON llm_models (provider_id);

CREATE INDEX IF NOT EXISTS idx_llm_models_code 
ON llm_models (model_code);

CREATE INDEX IF NOT EXISTS idx_llm_models_active 
ON llm_models (is_active);

CREATE INDEX IF NOT EXISTS idx_llm_models_default 
ON llm_models (is_default);

-- 复合索引：提供商 + 默认模型
CREATE INDEX IF NOT EXISTS idx_llm_models_provider_default 
ON llm_models (provider_id, is_default);

-- user_llm_configs 表
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user 
ON user_llm_configs (user_id);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_provider 
ON user_llm_configs (provider_id);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_model 
ON user_llm_configs (model_id);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_active 
ON user_llm_configs (is_active);

-- 复合索引：用户 + 激活状态
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user_active 
ON user_llm_configs (user_id, is_active);

-- =====================================================
-- 6. ai_parsing_history 表索引（如果存在）
-- =====================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ai_parsing_history') THEN
        -- 病案ID索引
        CREATE INDEX IF NOT EXISTS idx_ai_parsing_record 
        ON ai_parsing_history (record_id);
        
        -- 创建时间索引
        CREATE INDEX IF NOT EXISTS idx_ai_parsing_created 
        ON ai_parsing_history (created_at DESC);
        
        -- 提供商索引
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'ai_parsing_history' 
            AND column_name = 'provider_used'
        ) THEN
            CREATE INDEX IF NOT EXISTS idx_ai_parsing_provider 
            ON ai_parsing_history (provider_used);
        END IF;
        
        -- 模型索引
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = 'ai_parsing_history' 
            AND column_name = 'model_used'
        ) THEN
            CREATE INDEX IF NOT EXISTS idx_ai_parsing_model 
            ON ai_parsing_history (model_used);
        END IF;
    END IF;
END $$;

-- =====================================================
-- 7. 验证索引创建
-- =====================================================

-- 查询所有新创建的索引
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- =====================================================
-- 8. 索引使用统计（可选，用于监控）
-- =====================================================

-- 创建视图以监控索引使用情况
CREATE OR REPLACE VIEW index_usage_stats AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- =====================================================
-- 完成
-- =====================================================

-- 输出完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ 性能优化索引创建完成！';
    RAISE NOTICE '📊 已创建的索引数量: %', (
        SELECT COUNT(*) 
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND indexname LIKE 'idx_%'
    );
END $$;

