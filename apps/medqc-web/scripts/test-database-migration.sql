-- 数据库迁移测试脚本
-- 验证增强质控系统的数据库结构

-- 1. 测试表结构是否正确创建
\echo '🔍 检查表结构...'

-- 检查 qc_rules 表
SELECT 
    'qc_rules' as table_name,
    COUNT(*) as column_count,
    ARRAY_AGG(column_name ORDER BY ordinal_position) as columns
FROM information_schema.columns 
WHERE table_name = 'qc_rules' AND table_schema = 'public'
GROUP BY table_name;

-- 检查 qc_rule_executions 表
SELECT 
    'qc_rule_executions' as table_name,
    COUNT(*) as column_count,
    ARRAY_AGG(column_name ORDER BY ordinal_position) as columns
FROM information_schema.columns 
WHERE table_name = 'qc_rule_executions' AND table_schema = 'public'
GROUP BY table_name;

-- 检查 qc_issues 表
SELECT 
    'qc_issues' as table_name,
    COUNT(*) as column_count,
    ARRAY_AGG(column_name ORDER BY ordinal_position) as columns
FROM information_schema.columns 
WHERE table_name = 'qc_issues' AND table_schema = 'public'
GROUP BY table_name;

-- 2. 测试插入默认规则数据
\echo '📝 测试默认规则数据...'

-- 查看插入的规则数量
SELECT 
    category,
    COUNT(*) as rule_count,
    ARRAY_AGG(rule_code ORDER BY rule_code) as rule_codes
FROM qc_rules 
GROUP BY category 
ORDER BY category;

-- 查看规则类型分布
SELECT 
    rule_type,
    COUNT(*) as count,
    ROUND(AVG(max_score), 2) as avg_max_score,
    ROUND(AVG(weight), 2) as avg_weight
FROM qc_rules 
GROUP BY rule_type 
ORDER BY rule_type;

-- 查看严重程度分布
SELECT 
    severity,
    COUNT(*) as count,
    ARRAY_AGG(DISTINCT category) as categories
FROM qc_rules 
GROUP BY severity 
ORDER BY severity;

-- 3. 测试索引是否正确创建
\echo '🔍 检查索引...'

SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes 
WHERE tablename IN ('qc_rules', 'qc_rule_executions', 'qc_issues')
ORDER BY tablename, indexname;

-- 4. 测试视图是否正确创建
\echo '📊 检查视图...'

SELECT 
    viewname,
    definition
FROM pg_views 
WHERE viewname = 'qc_rule_execution_summary';

-- 5. 测试函数是否正确创建
\echo '🔧 检查函数...'

SELECT 
    routine_name,
    routine_type,
    data_type as return_type
FROM information_schema.routines 
WHERE routine_name = 'get_qc_rule_statistics' AND routine_schema = 'public';

-- 6. 测试触发器是否正确创建
\echo '⚡ 检查触发器...'

SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers 
WHERE trigger_name = 'update_qc_rules_updated_at';

-- 7. 测试RLS策略是否正确创建
\echo '🔒 检查RLS策略...'

SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies 
WHERE tablename IN ('qc_rules', 'qc_rule_executions', 'qc_issues')
ORDER BY tablename, policyname;

-- 8. 测试数据完整性约束
\echo '✅ 检查约束...'

SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name IN ('qc_rules', 'qc_rule_executions', 'qc_issues')
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;

-- 9. 测试外键关系
\echo '🔗 检查外键关系...'

SELECT 
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_name IN ('qc_rules', 'qc_rule_executions', 'qc_issues')
ORDER BY tc.table_name, kcu.column_name;

-- 10. 测试插入和查询功能
\echo '🧪 测试基本CRUD操作...'

-- 测试插入测试数据
INSERT INTO qc_rules (rule_code, name, description, category, rule_type, severity, max_score, weight)
VALUES ('TEST_001', '测试规则', '这是一个测试规则', 'completeness', 'objective', 'minor', 100, 1.0)
ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = NOW();

-- 验证插入成功
SELECT 
    rule_code,
    name,
    category,
    rule_type,
    severity,
    is_active,
    created_at,
    updated_at
FROM qc_rules 
WHERE rule_code = 'TEST_001';

-- 测试更新操作
UPDATE qc_rules 
SET description = '更新后的测试规则描述'
WHERE rule_code = 'TEST_001';

-- 验证更新成功
SELECT 
    rule_code,
    description,
    updated_at
FROM qc_rules 
WHERE rule_code = 'TEST_001';

-- 11. 测试统计函数
\echo '📈 测试统计函数...'

-- 测试统计函数（使用默认参数）
SELECT * FROM get_qc_rule_statistics();

-- 测试带参数的统计函数
SELECT * FROM get_qc_rule_statistics(NULL, '2024-01-01', '2024-12-31');

-- 12. 性能测试
\echo '⚡ 性能测试...'

-- 测试查询性能
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM qc_rules WHERE category = 'completeness' AND is_active = true;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM qc_rule_execution_summary LIMIT 10;

-- 13. 清理测试数据
\echo '🧹 清理测试数据...'

DELETE FROM qc_rules WHERE rule_code = 'TEST_001';

-- 验证清理成功
SELECT COUNT(*) as remaining_test_rules FROM qc_rules WHERE rule_code = 'TEST_001';

-- 14. 总结报告
\echo '📊 数据库迁移测试总结...'

SELECT 
    'qc_rules' as table_name,
    COUNT(*) as total_rules,
    COUNT(*) FILTER (WHERE is_active = true) as active_rules,
    COUNT(DISTINCT category) as categories,
    COUNT(DISTINCT rule_type) as rule_types,
    COUNT(DISTINCT severity) as severity_levels
FROM qc_rules

UNION ALL

SELECT 
    'database_tables' as table_name,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE table_name IN ('qc_rules', 'qc_rule_executions', 'qc_issues')) as qc_tables,
    0 as categories,
    0 as rule_types,
    0 as severity_levels
FROM information_schema.tables 
WHERE table_schema = 'public'

UNION ALL

SELECT 
    'indexes' as table_name,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE tablename IN ('qc_rules', 'qc_rule_executions', 'qc_issues')) as qc_indexes,
    0 as categories,
    0 as rule_types,
    0 as severity_levels
FROM pg_indexes 
WHERE schemaname = 'public';

\echo '✅ 数据库迁移测试完成！' 