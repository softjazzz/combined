-- ============================================================================
-- 验证 Migration 009 是否成功执行（Supabase Dashboard 版本）
-- ============================================================================

-- 1. 检查新增字段（应该返回 11 行）
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

-- 预期：11 行

-- ============================================================================

-- 2. 检查审计日志表（应该返回 1 行）
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_name = 'qc_rule_change_logs';

-- 预期：1 行，table_type = 'BASE TABLE'

-- ============================================================================

-- 3. 检查 departments 表（应该返回 1 行）
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_name = 'departments';

-- 预期：1 行，table_type = 'BASE TABLE'

-- ============================================================================

-- 4. 检查 RPC 函数（应该返回 2 行）
SELECT 
    proname AS function_name,
    pronargs AS num_args
FROM pg_proc
WHERE proname IN ('get_applicable_qc_rules', 'log_qc_rule_changes')
ORDER BY proname;

-- 预期：2 行
-- get_applicable_qc_rules (3 个参数)
-- log_qc_rule_changes (0 个参数)

-- ============================================================================

-- 5. 检查索引（应该返回 7 行）
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

-- 预期：7 行

-- ============================================================================

-- 6. 检查约束（应该返回 1 行）
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'qc_rules'
AND constraint_name = 'chk_department_scope';

-- 预期：1 行，constraint_type = 'CHECK'

-- ============================================================================

-- 7. 检查触发器（应该返回 3 行：INSERT, UPDATE, DELETE）
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table
FROM information_schema.triggers
WHERE trigger_name = 'trigger_log_qc_rule_changes'
ORDER BY event_manipulation;

-- 预期：3 行（INSERT, UPDATE, DELETE）

-- ============================================================================

-- 8. 检查视图（应该返回 2 行）
SELECT 
    table_name,
    table_type
FROM information_schema.tables
WHERE table_type = 'VIEW'
AND table_name IN ('qc_rules_department_statistics', 'qc_rules_by_department')
ORDER BY table_name;

-- 预期：2 行

-- ============================================================================

-- 9. 检查数据（所有现有规则应该是 global/published）
SELECT 
    scope,
    status,
    COUNT(*) AS count
FROM qc_rules
GROUP BY scope, status
ORDER BY scope, status;

-- 预期：至少 1 行，scope = 'global', status = 'published'

-- ============================================================================

-- 10. 检查科室表（应该返回 8 个示例科室）
SELECT 
    code,
    name,
    is_active
FROM departments
ORDER BY code;

-- 预期：8 行（DEPT_001 到 DEPT_008）

-- ============================================================================

-- 11. 测试 RPC 函数（应该返回规则列表）
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

-- 预期：返回规则列表（至少有一些全局规则）

-- ============================================================================

-- 12. 综合验证
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
    RAISE NOTICE '=== Verification Summary ===';
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
    
    RAISE NOTICE '';
    RAISE NOTICE 'Verification completed at: %', NOW();
END $$;

