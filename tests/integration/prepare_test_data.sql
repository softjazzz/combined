-- ============================================================================
-- 科室级质控规则集成测试 - 测试数据准备脚本
-- ============================================================================
-- 
-- 用途：为集成测试准备必要的测试数据
-- 包括：科室、全局规则、测试用户
--
-- 使用方法：
--   psql -h <host> -U postgres -d postgres -f prepare_test_data.sql
--
-- ============================================================================

-- 清理旧的测试数据
DO $$
BEGIN
    -- 删除测试科室规则
    DELETE FROM qc_rules WHERE scope = 'department' AND rule_code LIKE 'TEST_%';
    
    -- 删除测试全局规则
    DELETE FROM qc_rules WHERE scope = 'global' AND rule_code LIKE 'TEST_%';
    
    -- 删除测试科室
    DELETE FROM departments WHERE code LIKE 'TEST_%';
    
    RAISE NOTICE '✓ 清理旧的测试数据完成';
END $$;

-- ============================================================================
-- 1. 创建测试科室
-- ============================================================================

INSERT INTO departments (id, name, code, description, is_active, created_at, updated_at)
VALUES 
    (gen_random_uuid(), '测试心内科', 'TEST_CARDIO', '心血管内科测试科室', true, NOW(), NOW()),
    (gen_random_uuid(), '测试外科', 'TEST_SURGERY', '普通外科测试科室', true, NOW(), NOW()),
    (gen_random_uuid(), '测试儿科', 'TEST_PEDIATRICS', '儿科测试科室', true, NOW(), NOW()),
    (gen_random_uuid(), '测试妇产科', 'TEST_OBGYN', '妇产科测试科室', true, NOW(), NOW())
ON CONFLICT (code) DO NOTHING;

-- 验证科室创建
DO $$
DECLARE
    dept_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dept_count FROM departments WHERE code LIKE 'TEST_%';
    RAISE NOTICE '✓ 创建测试科室: % 个', dept_count;
END $$;

-- ============================================================================
-- 2. 创建测试全局规则
-- ============================================================================

-- 完整性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, is_active, check_logic, scoring_config, applicable_documents,
    created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'TEST_COMP_001',
    '测试-基本信息完整性',
    '检查病历基本信息是否完整（测试用）',
    'completeness',
    'critical',
    'logical',
    'global',
    true,
    '{"fields": ["patient_name", "patient_id", "admission_date"]}'::jsonb,
    '{"max_score": 10, "deduct_per_missing": 2}'::jsonb,
    ARRAY['入院记录', '病程记录'],
    NOW(),
    NOW()
);

-- 一致性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, is_active, check_logic, scoring_config, applicable_documents,
    created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'TEST_CONS_001',
    '测试-诊断一致性',
    '检查入院诊断与出院诊断是否一致（测试用）',
    'consistency',
    'major',
    'logical',
    'global',
    true,
    '{"compare_fields": ["admission_diagnosis", "discharge_diagnosis"]}'::jsonb,
    '{"max_score": 8, "deduct_inconsistent": 3}'::jsonb,
    ARRAY['入院记录', '出院记录'],
    NOW(),
    NOW()
);

-- 及时性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, is_active, check_logic, scoring_config, applicable_documents,
    created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'TEST_TIME_001',
    '测试-病程记录及时性',
    '检查病程记录是否按时完成（测试用）',
    'timeliness',
    'major',
    'logical',
    'global',
    true,
    '{"max_delay_hours": 24}'::jsonb,
    '{"max_score": 5, "deduct_per_hour": 0.5}'::jsonb,
    ARRAY['病程记录'],
    NOW(),
    NOW()
);

-- 准确性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, is_active, check_logic, scoring_config, applicable_documents,
    created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'TEST_ACC_001',
    '测试-医嘱准确性',
    '检查医嘱内容是否准确（测试用）',
    'accuracy',
    'critical',
    'semantic',
    'global',
    true,
    '{"check_drug_dosage": true, "check_contraindications": true}'::jsonb,
    '{"max_score": 10, "deduct_per_error": 5}'::jsonb,
    ARRAY['医嘱单'],
    NOW(),
    NOW()
);

-- 合理性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, is_active, check_logic, scoring_config, applicable_documents,
    created_at, updated_at
)
VALUES (
    gen_random_uuid(),
    'TEST_RAT_001',
    '测试-用药合理性',
    '检查用药是否合理（测试用）',
    'rationality',
    'major',
    'semantic',
    'global',
    true,
    '{"check_drug_interaction": true, "check_allergy": true}'::jsonb,
    '{"max_score": 8, "deduct_per_issue": 2}'::jsonb,
    ARRAY['医嘱单', '病程记录'],
    NOW(),
    NOW()
);

-- 验证全局规则创建
DO $$
DECLARE
    rule_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO rule_count FROM qc_rules WHERE scope = 'global' AND rule_code LIKE 'TEST_%';
    RAISE NOTICE '✓ 创建测试全局规则: % 条', rule_count;
END $$;

-- ============================================================================
-- 3. 创建测试用户（如果不存在）
-- ============================================================================

-- 注意：这里假设使用 Supabase Auth，实际用户创建可能需要通过 Supabase API
-- 这里只是示例，实际环境中可能需要手动创建用户

-- 创建测试管理员用户的角色记录（假设用户已在 auth.users 中）
-- INSERT INTO user_roles (user_id, role, department_id, created_at)
-- VALUES 
--     ('test-admin-uuid', 'ADMIN', NULL, NOW()),
--     ('test-qc-manager-uuid', 'QC_MANAGER', (SELECT id FROM departments WHERE code = 'TEST_CARDIO' LIMIT 1), NOW())
-- ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. 验证测试数据
-- ============================================================================

DO $$
DECLARE
    dept_count INTEGER;
    global_rule_count INTEGER;
BEGIN
    -- 统计科室数量
    SELECT COUNT(*) INTO dept_count FROM departments WHERE code LIKE 'TEST_%';
    
    -- 统计全局规则数量
    SELECT COUNT(*) INTO global_rule_count FROM qc_rules WHERE scope = 'global' AND rule_code LIKE 'TEST_%';
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '测试数据准备完成';
    RAISE NOTICE '========================================';
    RAISE NOTICE '测试科室数量: %', dept_count;
    RAISE NOTICE '测试全局规则数量: %', global_rule_count;
    RAISE NOTICE '';
    RAISE NOTICE '下一步：运行集成测试脚本';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- 5. 查询测试数据（用于验证）
-- ============================================================================

-- 查看测试科室
SELECT 
    id,
    name,
    code,
    description,
    is_active
FROM departments 
WHERE code LIKE 'TEST_%'
ORDER BY code;

-- 查看测试全局规则
SELECT 
    id,
    rule_code,
    name,
    category,
    severity,
    scope,
    is_active,
    array_length(applicable_documents, 1) as doc_count
FROM qc_rules 
WHERE scope = 'global' AND rule_code LIKE 'TEST_%'
ORDER BY rule_code;

-- ============================================================================
-- 完成
-- ============================================================================

