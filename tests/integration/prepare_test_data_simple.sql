-- ============================================================================
-- 科室级质控规则集成测试 - 简化测试数据准备脚本
-- ============================================================================
-- 使用固定 UUID，方便测试
-- ============================================================================

-- 清理旧的测试数据（不删除科室以避免外键冲突）
DELETE FROM qc_rules WHERE scope = 'department' AND rule_code LIKE 'TEST_%';
DELETE FROM qc_rules WHERE scope = 'global' AND rule_code LIKE 'TEST_%';
-- 保留测试科室，使用 UPSERT 更新（避免触发 user_profiles 外键约束）

-- ============================================================================
-- 1. 创建测试科室（使用固定 UUID）
-- ============================================================================

INSERT INTO departments (id, code, name, description, is_active, created_at, updated_at)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'TEST_CARDIO', '测试心内科', '心血管内科测试科室', true, NOW(), NOW()),
    ('22222222-2222-2222-2222-222222222222', 'TEST_SURGERY', '测试外科', '普通外科测试科室', true, NOW(), NOW()),
    ('33333333-3333-3333-3333-333333333333', 'TEST_PEDIATRICS', '测试儿科', '儿科测试科室', true, NOW(), NOW()),
    ('44444444-4444-4444-4444-444444444444', 'TEST_OBGYN', '测试妇产科', '妇产科测试科室', true, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    code = EXCLUDED.code,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ============================================================================
-- 2. 创建测试全局规则（使用固定 UUID）
-- ============================================================================

-- 完整性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, status, is_active, priority,
    check_logic, scoring_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'TEST_COMP_001',
    '测试-基本信息完整性',
    '检查病历基本信息是否完整（测试用）',
    'completeness',
    'critical',
    'logical',
    'global',
    'published',
    true,
    0,
    '{"fields": ["patient_name", "patient_id", "admission_date"]}'::jsonb,
    '{"max_score": 10, "deduct_per_missing": 2}'::jsonb,
    ARRAY['入院记录', '病程记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- 一致性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, status, is_active, priority,
    check_logic, scoring_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'TEST_CONS_001',
    '测试-诊断一致性',
    '检查入院诊断与出院诊断是否一致（测试用）',
    'consistency',
    'major',
    'logical',
    'global',
    'published',
    true,
    0,
    '{"compare_fields": ["admission_diagnosis", "discharge_diagnosis"]}'::jsonb,
    '{"max_score": 8, "deduct_inconsistent": 3}'::jsonb,
    ARRAY['入院记录', '出院记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- 及时性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, status, is_active, priority,
    check_logic, scoring_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    'TEST_TIME_001',
    '测试-病程记录及时性',
    '检查病程记录是否按时完成（测试用）',
    'timeliness',
    'major',
    'logical',
    'global',
    'published',
    true,
    0,
    '{"max_hours": 24}'::jsonb,
    '{"max_score": 5, "deduct_per_hour": 0.5}'::jsonb,
    ARRAY['病程记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- 合理性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, status, is_active, priority,
    check_logic, scoring_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'TEST_RATI_001',
    '测试-用药合理性',
    '检查用药是否合理（测试用）',
    'completeness',
    'critical',
    'hybrid',
    'global',
    'published',
    true,
    0,
    '{"check_drug_interaction": true}'::jsonb,
    '{"max_score": 15, "deduct_per_issue": 5}'::jsonb,
    ARRAY['医嘱记录', '用药记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- 规范性规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, status, is_active, priority,
    check_logic, scoring_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
    'TEST_NORM_001',
    '测试-病历书写规范',
    '检查病历书写是否符合规范（测试用）',
    'completeness',
    'minor',
    'semantic',
    'global',
    'published',
    true,
    0,
    '{"check_format": true, "check_terminology": true}'::jsonb,
    '{"max_score": 5, "deduct_per_issue": 1}'::jsonb,
    ARRAY['入院记录', '病程记录', '出院记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- 3. 创建测试科室规则（覆盖全局规则）
-- ============================================================================

-- 心内科覆盖完整性规则（提高优先级和扣分）
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, department_id, parent_rule_id, override_action,
    status, is_active, priority,
    check_logic, scoring_config, override_config, applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    'ffffffff-ffff-ffff-ffff-ffffffffffff',
    'TEST_COMP_001_C',
    '测试-基本信息完整性（心内科定制）',
    '心内科的基本信息完整性检查，要求更严格（测试用）',
    'completeness',
    'critical',
    'logical',
    'department',
    '11111111-1111-1111-1111-111111111111',  -- 测试心内科
    (SELECT id FROM qc_rules WHERE rule_code = 'TEST_COMP_001'),  -- 父规则
    'override',
    'published',
    true,
    10,  -- 更高优先级
    '{"fields": ["patient_name", "patient_id", "admission_date", "chief_complaint", "present_illness"]}'::jsonb,
    '{"max_score": 15, "deduct_per_missing": 3}'::jsonb,
    '{"overridden_fields": ["check_logic", "scoring_config"]}'::jsonb,
    ARRAY['入院记录', '病程记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- 儿科禁用成人用药规则
INSERT INTO qc_rules (
    id, rule_code, name, description, category, severity, rule_type,
    scope, department_id, parent_rule_id, override_action,
    status, is_active, priority,
    applicable_documents,
    created_at, updated_at, created_by
)
VALUES (
    '99999999-9999-9999-9999-999999999999',
    'TEST_RATI_001_PD',
    '测试-禁用成人用药规则',
    '儿科使用儿童用药标准，禁用成人用药规则（测试用）',
    'completeness',
    'critical',
    'hybrid',
    'department',
    '33333333-3333-3333-3333-333333333333',  -- 测试儿科
    (SELECT id FROM qc_rules WHERE rule_code = 'TEST_RATI_001'),  -- 父规则
    'disable',
    'published',
    true,
    0,
    ARRAY['医嘱记录', '用药记录'],
    NOW(),
    NOW(),
    (SELECT id FROM user_profiles ORDER BY created_at LIMIT 1)
)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- 验证测试数据
-- ============================================================================

DO $$
DECLARE
    v_dept_count INTEGER;
    v_global_rule_count INTEGER;
    v_dept_rule_count INTEGER;
    v_info TEXT;
BEGIN
    SELECT COUNT(*) INTO v_dept_count FROM departments WHERE code LIKE 'TEST_%';
    SELECT COUNT(*) INTO v_global_rule_count FROM qc_rules WHERE scope = 'global' AND rule_code LIKE 'TEST_%';
    SELECT COUNT(*) INTO v_dept_rule_count FROM qc_rules WHERE scope = 'department' AND rule_code LIKE 'TEST_%';

    RAISE NOTICE '╔════════════════════════════════════════════════════════════╗';
    RAISE NOTICE '║  ✅ 测试数据准备完成                                      ║';
    RAISE NOTICE '╠════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  测试科室: % 个                                           ║', v_dept_count;
    RAISE NOTICE '║  全局测试规则: % 个                                       ║', v_global_rule_count;
    RAISE NOTICE '║  科室测试规则: % 个                                       ║', v_dept_rule_count;
    RAISE NOTICE '╚════════════════════════════════════════════════════════════╝';

    -- 显示科室列表
    RAISE NOTICE '';
    RAISE NOTICE '测试科室列表:';
    FOR v_info IN
        SELECT code || ' - ' || name AS info
        FROM departments
        WHERE code LIKE 'TEST_%'
        ORDER BY code
    LOOP
        RAISE NOTICE '  • %', v_info;
    END LOOP;
END $$;

-- 显示规则统计
SELECT 
    scope,
    status,
    COUNT(*) AS count
FROM qc_rules
WHERE rule_code LIKE 'TEST_%'
GROUP BY scope, status
ORDER BY scope, status;

