-- verify_009.sql
-- 验证 Migration 009 是否成功执行
--
-- 使用方法：
-- psql -h localhost -U postgres -d medqc -f verify_009.sql
--
-- 版本: 2.0
-- 创建日期: 2025-10-12

\echo '=== Verifying Migration 009: Department QC Rules ==='
\echo ''

-- ============================================================================
-- 1. 验证表结构
-- ============================================================================

\echo '1. Checking table structure...'

-- 检查 qc_rules 表的新增字段
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'qc_rules'
AND column_name IN (
    'scope', 'department_id', 'parent_rule_id', 'override_action',
    'override_config', 'priority', 'status', 'effective_from',
    'effective_to', 'approved_by', 'approved_at'
)
ORDER BY column_name;

\echo ''
\echo '✓ Expected 11 columns above'
\echo ''

-- 检查 qc_rule_change_logs 表
SELECT 
    table_name,
    table_type
FROM information_schema.tables
WHERE table_name = 'qc_rule_change_logs';

\echo ''
\echo '✓ qc_rule_change_logs table should exist'
\echo ''

-- 检查 departments 表
SELECT 
    table_name,
    table_type
FROM information_schema.tables
WHERE table_name = 'departments';

\echo ''
\echo '✓ departments table should exist'
\echo ''

-- ============================================================================
-- 2. 验证索引
-- ============================================================================

\echo '2. Checking indexes...'

SELECT 
    indexname,
    tablename
FROM pg_indexes
WHERE tablename = 'qc_rules'
AND indexname IN (
    'uk_dept_rule_code_published',
    'idx_qc_rules_scope',
    'idx_qc_rules_department',
    'idx_qc_rules_parent',
    'idx_qc_rules_status',
    'idx_qc_rules_effective',
    'idx_qc_rules_composite'
)
ORDER BY indexname;

\echo ''
\echo '✓ Expected 7 indexes above'
\echo ''

-- ============================================================================
-- 3. 验证约束
-- ============================================================================

\echo '3. Checking constraints...'

SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'qc_rules'
AND constraint_name = 'chk_department_scope';

\echo ''
\echo '✓ chk_department_scope constraint should exist'
\echo ''

-- ============================================================================
-- 4. 验证函数
-- ============================================================================

\echo '4. Checking functions...'

SELECT 
    proname AS function_name,
    pronargs AS num_args
FROM pg_proc
WHERE proname IN ('get_applicable_qc_rules', 'log_qc_rule_changes')
ORDER BY proname;

\echo ''
\echo '✓ Expected 2 functions above'
\echo ''

-- ============================================================================
-- 5. 验证触发器
-- ============================================================================

\echo '5. Checking triggers...'

SELECT 
    trigger_name,
    event_manipulation,
    event_object_table
FROM information_schema.triggers
WHERE trigger_name = 'trigger_log_qc_rule_changes';

\echo ''
\echo '✓ trigger_log_qc_rule_changes should exist'
\echo ''

-- ============================================================================
-- 6. 验证视图
-- ============================================================================

\echo '6. Checking views...'

SELECT 
    table_name,
    table_type
FROM information_schema.tables
WHERE table_type = 'VIEW'
AND table_name IN ('qc_rules_department_statistics', 'qc_rules_by_department')
ORDER BY table_name;

\echo ''
\echo '✓ Expected 2 views above'
\echo ''

-- ============================================================================
-- 7. 验证数据
-- ============================================================================

\echo '7. Checking data...'

-- 统计规则数量
SELECT 
    scope,
    status,
    COUNT(*) AS count
FROM qc_rules
GROUP BY scope, status
ORDER BY scope, status;

\echo ''
\echo '✓ All existing rules should be global/published'
\echo ''

-- 检查科室数据
SELECT 
    code,
    name,
    is_active
FROM departments
ORDER BY code
LIMIT 10;

\echo ''
\echo '✓ Sample departments should exist'
\echo ''

-- ============================================================================
-- 8. 测试 RPC 函数
-- ============================================================================

\echo '8. Testing RPC function...'

-- 测试获取适用规则（使用第一个科室）
SELECT 
    rule_code,
    name,
    source,
    priority
FROM get_applicable_qc_rules(
    (SELECT id FROM departments LIMIT 1),
    NULL,
    NOW()
)
LIMIT 5;

\echo ''
\echo '✓ RPC function should return rules'
\echo ''

-- ============================================================================
-- 9. 测试触发器
-- ============================================================================

\echo '9. Testing trigger (creating test rule)...'

-- 创建测试规则
DO $$
DECLARE
    v_test_rule_id UUID;
    v_log_count INTEGER;
BEGIN
    -- 插入测试规则
    INSERT INTO qc_rules (
        rule_code, name, description, category, rule_type, severity,
        scope, status, check_logic, scoring_config
    ) VALUES (
        'TEST_VERIFY_009', '测试规则', '用于验证触发器', 
        'completeness', 'objective', 'minor',
        'global', 'draft', '{}', '{}'
    ) RETURNING id INTO v_test_rule_id;
    
    -- 检查审计日志
    SELECT COUNT(*) INTO v_log_count
    FROM qc_rule_change_logs
    WHERE rule_id = v_test_rule_id
    AND action = 'create';
    
    IF v_log_count = 1 THEN
        RAISE NOTICE '✓ Trigger created audit log successfully';
    ELSE
        RAISE WARNING '✗ Trigger did not create audit log (found % logs)', v_log_count;
    END IF;
    
    -- 清理测试数据
    DELETE FROM qc_rules WHERE id = v_test_rule_id;
    
    RAISE NOTICE '✓ Test rule cleaned up';
END $$;

\echo ''

-- ============================================================================
-- 10. 总结
-- ============================================================================

\echo '=== Verification Summary ==='
\echo ''

DO $$
DECLARE
    v_columns_count INTEGER;
    v_indexes_count INTEGER;
    v_functions_count INTEGER;
    v_views_count INTEGER;
    v_all_passed BOOLEAN := true;
BEGIN
    -- 统计新增字段
    SELECT COUNT(*) INTO v_columns_count
    FROM information_schema.columns
    WHERE table_name = 'qc_rules'
    AND column_name IN (
        'scope', 'department_id', 'parent_rule_id', 'override_action',
        'override_config', 'priority', 'status', 'effective_from',
        'effective_to', 'approved_by', 'approved_at'
    );
    
    -- 统计索引
    SELECT COUNT(*) INTO v_indexes_count
    FROM pg_indexes
    WHERE tablename = 'qc_rules'
    AND indexname IN (
        'uk_dept_rule_code_published',
        'idx_qc_rules_scope',
        'idx_qc_rules_department',
        'idx_qc_rules_parent',
        'idx_qc_rules_status',
        'idx_qc_rules_effective',
        'idx_qc_rules_composite'
    );
    
    -- 统计函数
    SELECT COUNT(*) INTO v_functions_count
    FROM pg_proc
    WHERE proname IN ('get_applicable_qc_rules', 'log_qc_rule_changes');
    
    -- 统计视图
    SELECT COUNT(*) INTO v_views_count
    FROM information_schema.tables
    WHERE table_type = 'VIEW'
    AND table_name IN ('qc_rules_department_statistics', 'qc_rules_by_department');
    
    -- 验证结果
    RAISE NOTICE 'Columns added: % (expected 11)', v_columns_count;
    IF v_columns_count != 11 THEN
        v_all_passed := false;
    END IF;
    
    RAISE NOTICE 'Indexes created: % (expected 7)', v_indexes_count;
    IF v_indexes_count != 7 THEN
        v_all_passed := false;
    END IF;
    
    RAISE NOTICE 'Functions created: % (expected 2)', v_functions_count;
    IF v_functions_count != 2 THEN
        v_all_passed := false;
    END IF;
    
    RAISE NOTICE 'Views created: % (expected 2)', v_views_count;
    IF v_views_count != 2 THEN
        v_all_passed := false;
    END IF;
    
    RAISE NOTICE '';
    
    IF v_all_passed THEN
        RAISE NOTICE '╔════════════════════════════════════════════════════════════╗';
        RAISE NOTICE '║  ✅ All Verifications PASSED!                             ║';
        RAISE NOTICE '║  Migration 009 executed successfully.                     ║';
        RAISE NOTICE '╚════════════════════════════════════════════════════════════╝';
    ELSE
        RAISE WARNING '╔════════════════════════════════════════════════════════════╗';
        RAISE WARNING '║  ⚠️  Some Verifications FAILED!                           ║';
        RAISE WARNING '║  Please check the output above for details.               ║';
        RAISE WARNING '╚════════════════════════════════════════════════════════════╝';
    END IF;
END $$;

\echo ''
\echo 'Verification completed at:' 
SELECT NOW();

