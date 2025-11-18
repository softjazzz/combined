-- ============================================================================
-- 数据库性能分析脚本
-- ============================================================================
-- 
-- 用途：分析科室级质控规则相关查询的性能
-- 使用 EXPLAIN ANALYZE 分析查询计划和执行时间
--
-- 使用方法：
--   psql -h <host> -U postgres -d postgres -f analyze_db_performance.sql
--
-- ============================================================================

\timing on

-- ============================================================================
-- 1. 分析规则列表查询性能
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 1: 规则列表查询性能'
\echo '========================================'
\echo ''

-- 查询所有科室规则（带分页）
EXPLAIN ANALYZE
SELECT 
    id, rule_code, name, description, category, severity,
    scope, department_id, parent_rule_id, override_action,
    priority, status, is_active, created_at, updated_at
FROM qc_rules
WHERE scope = 'department'
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;

\echo ''
\echo '分析：检查是否使用了索引，扫描行数是否合理'
\echo ''

-- ============================================================================
-- 2. 分析规则匹配查询性能（RPC 函数）
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 2: 规则匹配查询性能'
\echo '========================================'
\echo ''

-- 准备测试数据
DO $$
DECLARE
    test_dept_id UUID;
BEGIN
    -- 获取一个测试科室 ID
    SELECT id INTO test_dept_id FROM departments WHERE code LIKE 'TEST_%' LIMIT 1;
    
    IF test_dept_id IS NULL THEN
        RAISE NOTICE '警告: 没有找到测试科室，请先运行 prepare_test_data.sql';
        RETURN;
    END IF;
    
    RAISE NOTICE '使用测试科室 ID: %', test_dept_id;
    
    -- 分析 RPC 函数性能
    RAISE NOTICE '';
    RAISE NOTICE '执行 get_applicable_qc_rules RPC 函数...';
    RAISE NOTICE '';
END $$;

-- 注意：EXPLAIN ANALYZE 不能直接用于 RPC 函数调用
-- 我们需要手动展开 RPC 函数的逻辑来分析

-- 模拟 RPC 函数的查询逻辑
EXPLAIN ANALYZE
WITH 
-- 1. 获取全局规则
global_rules AS (
    SELECT 
        r.*,
        0 as effective_priority  -- 全局规则优先级为 0
    FROM qc_rules r
    WHERE r.scope = 'global'
      AND r.is_active = true
      AND r.status = 'published'
      AND (r.effective_from IS NULL OR r.effective_from <= NOW())
      AND (r.effective_to IS NULL OR r.effective_to >= NOW())
),

-- 2. 获取科室规则
department_rules AS (
    SELECT 
        r.*,
        r.priority as effective_priority
    FROM qc_rules r
    WHERE r.scope = 'department'
      AND r.department_id = (SELECT id FROM departments WHERE code LIKE 'TEST_%' LIMIT 1)
      AND r.is_active = true
      AND r.status = 'published'
      AND (r.effective_from IS NULL OR r.effective_from <= NOW())
      AND (r.effective_to IS NULL OR r.effective_to >= NOW())
),

-- 3. 合并规则（科室规则覆盖全局规则）
merged_rules AS (
    -- 科室规则
    SELECT * FROM department_rules
    
    UNION ALL
    
    -- 全局规则（排除被禁用的）
    SELECT * FROM global_rules g
    WHERE NOT EXISTS (
        SELECT 1 FROM department_rules d
        WHERE d.parent_rule_id = g.id
          AND d.override_action = 'disable'
    )
    -- 排除被覆盖的
    AND NOT EXISTS (
        SELECT 1 FROM department_rules d
        WHERE d.parent_rule_id = g.id
          AND d.override_action = 'override'
    )
)

-- 4. 返回结果（按优先级排序）
SELECT 
    id, rule_code, name, category, severity,
    scope, department_id, priority, status
FROM merged_rules
ORDER BY effective_priority DESC, created_at DESC;

\echo ''
\echo '分析：检查 CTE 的执行计划，是否有全表扫描'
\echo ''

-- ============================================================================
-- 3. 分析索引使用情况
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 3: 索引使用情况'
\echo '========================================'
\echo ''

-- 查看 qc_rules 表的索引
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'qc_rules'
ORDER BY indexname;

\echo ''

-- 查看索引大小
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE tablename = 'qc_rules'
ORDER BY pg_relation_size(indexname::regclass) DESC;

\echo ''

-- ============================================================================
-- 4. 分析变更历史查询性能
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 4: 变更历史查询性能'
\echo '========================================'
\echo ''

-- 查询某个规则的变更历史
EXPLAIN ANALYZE
SELECT 
    id, rule_id, department_id, action,
    old_values, new_values, diff,
    actor_id, reason, created_at
FROM qc_rule_change_logs
WHERE rule_id = (SELECT id FROM qc_rules WHERE rule_code LIKE 'TEST_%' LIMIT 1)
ORDER BY created_at DESC
LIMIT 10;

\echo ''
\echo '分析：检查是否使用了 rule_id 索引'
\echo ''

-- ============================================================================
-- 5. 分析表统计信息
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 5: 表统计信息'
\echo '========================================'
\echo ''

-- qc_rules 表统计
SELECT 
    'qc_rules' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE scope = 'global') as global_rules,
    COUNT(*) FILTER (WHERE scope = 'department') as department_rules,
    COUNT(*) FILTER (WHERE status = 'published') as published_rules,
    COUNT(*) FILTER (WHERE status = 'draft') as draft_rules,
    COUNT(*) FILTER (WHERE is_active = true) as active_rules
FROM qc_rules;

\echo ''

-- qc_rule_change_logs 表统计
SELECT 
    'qc_rule_change_logs' as table_name,
    COUNT(*) as total_logs,
    COUNT(DISTINCT rule_id) as rules_with_logs,
    COUNT(*) FILTER (WHERE action = 'create') as create_actions,
    COUNT(*) FILTER (WHERE action = 'update') as update_actions,
    COUNT(*) FILTER (WHERE action = 'delete') as delete_actions,
    COUNT(*) FILTER (WHERE action = 'publish') as publish_actions
FROM qc_rule_change_logs;

\echo ''

-- ============================================================================
-- 6. 分析慢查询（如果有）
-- ============================================================================

\echo ''
\echo '========================================'
\echo '测试 6: 慢查询分析'
\echo '========================================'
\echo ''

-- 检查是否启用了 pg_stat_statements 扩展
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ pg_stat_statements 已启用'
        ELSE '✗ pg_stat_statements 未启用'
    END as status
FROM pg_extension
WHERE extname = 'pg_stat_statements';

\echo ''

-- 如果启用了 pg_stat_statements，查询最慢的查询
-- SELECT 
--     query,
--     calls,
--     total_time,
--     mean_time,
--     max_time
-- FROM pg_stat_statements
-- WHERE query LIKE '%qc_rules%'
-- ORDER BY mean_time DESC
-- LIMIT 10;

-- ============================================================================
-- 7. 性能优化建议
-- ============================================================================

\echo ''
\echo '========================================'
\echo '性能优化建议'
\echo '========================================'
\echo ''
\echo '1. 确保以下索引存在：'
\echo '   - idx_qc_rules_scope_department'
\echo '   - idx_qc_rules_status_active'
\echo '   - idx_qc_rules_parent_rule'
\echo '   - idx_qc_rules_effective_period'
\echo '   - idx_qc_rule_change_logs_rule_id'
\echo ''
\echo '2. 定期运行 VACUUM ANALYZE：'
\echo '   VACUUM ANALYZE qc_rules;'
\echo '   VACUUM ANALYZE qc_rule_change_logs;'
\echo ''
\echo '3. 监控查询性能：'
\echo '   - 启用 pg_stat_statements 扩展'
\echo '   - 设置 log_min_duration_statement = 1000 (记录超过1秒的查询)'
\echo ''
\echo '4. 考虑分区表（如果数据量很大）：'
\echo '   - 按 department_id 分区'
\echo '   - 按 created_at 分区（时间序列数据）'
\echo ''
\echo '========================================'
\echo ''

-- ============================================================================
-- 完成
-- ============================================================================

\timing off

