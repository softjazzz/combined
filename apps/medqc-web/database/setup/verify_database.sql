-- =============================================
-- 医疗质控系统数据库验证脚本
-- 版本: 2.0.0
-- 创建时间: 2024-12-25
-- 用途: 验证数据库是否正确初始化
-- =============================================

-- 1. 检查扩展是否启用
SELECT 
    'Extensions Check' as check_category,
    extname as extension_name,
    'Enabled' as status
FROM pg_extension 
WHERE extname IN ('uuid-ossp', 'pg_trgm', 'btree_gin', 'vector')
ORDER BY extname;

-- 2. 检查所有表是否创建
SELECT 
    'Tables Check' as check_category,
    table_name,
    table_type,
    'Created' as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
AND table_name NOT LIKE 'pg_%'
AND table_name NOT LIKE 'sql_%'
ORDER BY table_name;

-- 3. 检查视图是否创建
SELECT 
    'Views Check' as check_category,
    viewname as view_name,
    'Created' as status
FROM pg_views 
WHERE schemaname = 'public'
ORDER BY viewname;

-- 4. 检查索引是否创建
SELECT 
    'Indexes Check' as check_category,
    indexname as index_name,
    tablename as table_name,
    'Created' as status
FROM pg_indexes 
WHERE schemaname = 'public'
AND indexname NOT LIKE 'pg_%'
AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- 5. 检查RLS策略是否启用
SELECT 
    'RLS Check' as check_category,
    schemaname,
    tablename,
    CASE WHEN rowsecurity THEN 'Enabled' ELSE 'Disabled' END as rls_status
FROM pg_tables 
WHERE schemaname = 'public'
AND tablename IN ('user_profiles', 'departments', 'medical_records', 'qc_rules', 'qc_results', 'batch_processing_tasks', 'alert_records')
ORDER BY tablename;

-- 6. 检查RLS策略详情
SELECT 
    'RLS Policies Check' as check_category,
    schemaname,
    tablename,
    policyname as policy_name,
    'Created' as status
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- 7. 检查触发器是否创建
SELECT 
    'Triggers Check' as check_category,
    trigger_name,
    event_object_table as table_name,
    'Created' as status
FROM information_schema.triggers 
WHERE trigger_schema = 'public'
AND trigger_name NOT LIKE 'pg_%'
ORDER BY event_object_table, trigger_name;

-- 8. 检查函数是否创建
SELECT 
    'Functions Check' as check_category,
    routine_name as function_name,
    routine_type,
    'Created' as status
FROM information_schema.routines 
WHERE routine_schema = 'public'
AND routine_name IN ('update_updated_at_column', 'calculate_word_count', 'cleanup_expired_cache')
ORDER BY routine_name;

-- 9. 检查初始数据
SELECT 
    'Initial Data Check' as check_category,
    'departments' as table_name,
    COUNT(*) as record_count,
    CASE WHEN COUNT(*) > 0 THEN 'Data Loaded' ELSE 'No Data' END as status
FROM departments
UNION ALL
SELECT 
    'Initial Data Check' as check_category,
    'analytics_metrics' as table_name,
    COUNT(*) as record_count,
    CASE WHEN COUNT(*) > 0 THEN 'Data Loaded' ELSE 'No Data' END as status
FROM analytics_metrics
UNION ALL
SELECT 
    'Initial Data Check' as check_category,
    'qc_rules' as table_name,
    COUNT(*) as record_count,
    CASE WHEN COUNT(*) > 0 THEN 'Data Loaded' ELSE 'No Data' END as status
FROM qc_rules;

-- 10. 检查外键约束
SELECT 
    'Foreign Keys Check' as check_category,
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    'Created' as status
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name;

-- 11. 检查约束条件
SELECT 
    'Constraints Check' as check_category,
    table_name,
    constraint_name,
    constraint_type,
    'Created' as status
FROM information_schema.table_constraints 
WHERE table_schema = 'public'
AND constraint_type IN ('CHECK', 'UNIQUE')
ORDER BY table_name, constraint_type, constraint_name;

-- 12. 数据库统计摘要
SELECT 
    'Database Summary' as check_category,
    'Total Tables' as metric,
    COUNT(*) as value,
    'Count' as unit
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
AND table_name NOT LIKE 'pg_%'
UNION ALL
SELECT 
    'Database Summary' as check_category,
    'Total Views' as metric,
    COUNT(*) as value,
    'Count' as unit
FROM pg_views 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'Database Summary' as check_category,
    'Total Indexes' as metric,
    COUNT(*) as value,
    'Count' as unit
FROM pg_indexes 
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%'
UNION ALL
SELECT 
    'Database Summary' as check_category,
    'Total RLS Policies' as metric,
    COUNT(*) as value,
    'Count' as unit
FROM pg_policies 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'Database Summary' as check_category,
    'Total Functions' as metric,
    COUNT(*) as value,
    'Count' as unit
FROM information_schema.routines 
WHERE routine_schema = 'public'
AND routine_name IN ('update_updated_at_column', 'calculate_word_count', 'cleanup_expired_cache');

-- 13. 表结构详情（主要表）
SELECT 
    'Table Structure Check' as check_category,
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public'
AND table_name IN ('user_profiles', 'departments', 'medical_records', 'qc_rules', 'qc_results')
ORDER BY table_name, ordinal_position;

-- 14. 最终验证状态
WITH validation_summary AS (
    SELECT 
        COUNT(CASE WHEN extname IN ('uuid-ossp', 'pg_trgm', 'btree_gin', 'vector') THEN 1 END) as extensions_count,
        (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name NOT LIKE 'pg_%') as tables_count,
        (SELECT COUNT(*) FROM pg_views WHERE schemaname = 'public') as views_count,
        (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%') as indexes_count,
        (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public') as policies_count,
        (SELECT COUNT(*) FROM departments) as departments_count,
        (SELECT COUNT(*) FROM analytics_metrics) as metrics_count
    FROM pg_extension
)
SELECT 
    'Final Validation' as check_category,
    CASE 
        WHEN extensions_count >= 4 
        AND tables_count >= 12 
        AND views_count >= 3 
        AND indexes_count >= 20 
        AND policies_count >= 8 
        AND departments_count >= 7 
        AND metrics_count >= 5 
        THEN '✅ Database Successfully Initialized'
        ELSE '❌ Database Initialization Incomplete'
    END as validation_result,
    CONCAT(
        'Extensions: ', extensions_count, '/4, ',
        'Tables: ', tables_count, '/12, ',
        'Views: ', views_count, '/3, ',
        'Indexes: ', indexes_count, '/20, ',
        'Policies: ', policies_count, '/8, ',
        'Departments: ', departments_count, '/7, ',
        'Metrics: ', metrics_count, '/5'
    ) as details
FROM validation_summary;
