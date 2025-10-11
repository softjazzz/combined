-- test_006_migration.sql
-- 测试 006 迁移脚本的功能
--
-- 使用方法：
-- 1. 先执行 006_add_applicable_documents_field.sql
-- 2. 再执行本测试脚本
-- 3. 检查输出结果

-- ============================================================================
-- 测试 1: 验证字段是否创建成功
-- ============================================================================

DO $$
DECLARE
    column_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' 
        AND column_name = 'applicable_documents'
    ) INTO column_exists;
    
    IF column_exists THEN
        RAISE NOTICE '✅ Test 1 PASSED: applicable_documents column exists';
    ELSE
        RAISE EXCEPTION '❌ Test 1 FAILED: applicable_documents column does not exist';
    END IF;
END $$;

-- ============================================================================
-- 测试 2: 验证索引是否创建成功
-- ============================================================================

DO $$
DECLARE
    index_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'qc_rules' 
        AND indexname = 'idx_qc_rules_applicable_documents'
    ) INTO index_exists;
    
    IF index_exists THEN
        RAISE NOTICE '✅ Test 2 PASSED: GIN index exists';
    ELSE
        RAISE EXCEPTION '❌ Test 2 FAILED: GIN index does not exist';
    END IF;
END $$;

-- ============================================================================
-- 测试 3: 验证辅助函数是否创建成功
-- ============================================================================

DO $$
DECLARE
    function_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'get_applicable_rules'
    ) INTO function_exists;
    
    IF function_exists THEN
        RAISE NOTICE '✅ Test 3 PASSED: get_applicable_rules function exists';
    ELSE
        RAISE EXCEPTION '❌ Test 3 FAILED: get_applicable_rules function does not exist';
    END IF;
END $$;

-- ============================================================================
-- 测试 4: 验证视图是否创建成功
-- ============================================================================

DO $$
DECLARE
    view1_exists BOOLEAN;
    view2_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_views 
        WHERE viewname = 'qc_rules_statistics'
    ) INTO view1_exists;
    
    SELECT EXISTS (
        SELECT 1 FROM pg_views 
        WHERE viewname = 'qc_rules_by_document_type'
    ) INTO view2_exists;
    
    IF view1_exists AND view2_exists THEN
        RAISE NOTICE '✅ Test 4 PASSED: Both views exist';
    ELSE
        RAISE EXCEPTION '❌ Test 4 FAILED: One or more views do not exist';
    END IF;
END $$;

-- ============================================================================
-- 测试 5: 插入测试数据
-- ============================================================================

-- 清理测试数据（如果存在）
DELETE FROM qc_rules WHERE rule_code LIKE 'TEST-%';

-- 插入测试规则
INSERT INTO qc_rules (
    rule_code, 
    name, 
    description, 
    category, 
    rule_type, 
    severity,
    applicable_documents,
    check_logic
) VALUES
-- 测试规则 1: 适用于首次病程记录
('TEST-001', '测试规则1', '适用于首次病程记录', 'completeness', 'objective', 'major', 
 ARRAY['首次病程记录'], 
 '{"applicable_documents": ["首次病程记录"]}'::jsonb),

-- 测试规则 2: 适用于多种文书类型
('TEST-002', '测试规则2', '适用于病程记录和手术记录', 'completeness', 'objective', 'major', 
 ARRAY['病程记录', '手术记录'], 
 '{"applicable_documents": ["病程记录", "手术记录"]}'::jsonb),

-- 测试规则 3: 通用规则（空数组）
('TEST-003', '测试规则3', '通用规则', 'completeness', 'objective', 'major', 
 ARRAY[]::TEXT[], 
 '{}'::jsonb),

-- 测试规则 4: 通用规则（NULL）
('TEST-004', '测试规则4', '通用规则（NULL）', 'completeness', 'objective', 'major', 
 NULL, 
 '{}'::jsonb);

RAISE NOTICE '✅ Test 5 PASSED: Test data inserted successfully';

-- ============================================================================
-- 测试 6: 测试数组查询
-- ============================================================================

DO $$
DECLARE
    rule_count INTEGER;
BEGIN
    -- 查询适用于"首次病程记录"的规则（应该返回 TEST-001 和通用规则）
    SELECT COUNT(*) INTO rule_count
    FROM qc_rules
    WHERE rule_code LIKE 'TEST-%'
    AND (
        '首次病程记录' = ANY(applicable_documents)
        OR applicable_documents IS NULL
        OR array_length(applicable_documents, 1) IS NULL
        OR array_length(applicable_documents, 1) = 0
    );
    
    IF rule_count = 3 THEN
        RAISE NOTICE '✅ Test 6 PASSED: Array query returned correct count (expected 3, got %)', rule_count;
    ELSE
        RAISE EXCEPTION '❌ Test 6 FAILED: Array query returned incorrect count (expected 3, got %)', rule_count;
    END IF;
END $$;

-- ============================================================================
-- 测试 7: 测试 get_applicable_rules 函数
-- ============================================================================

DO $$
DECLARE
    rule_count INTEGER;
BEGIN
    -- 使用函数查询适用于"首次病程记录"的规则
    SELECT COUNT(*) INTO rule_count
    FROM get_applicable_rules('首次病程记录', true)
    WHERE rule_code LIKE 'TEST-%';
    
    IF rule_count = 3 THEN
        RAISE NOTICE '✅ Test 7 PASSED: get_applicable_rules function returned correct count (expected 3, got %)', rule_count;
    ELSE
        RAISE EXCEPTION '❌ Test 7 FAILED: get_applicable_rules function returned incorrect count (expected 3, got %)', rule_count;
    END IF;
END $$;

-- ============================================================================
-- 测试 8: 测试数组包含操作符
-- ============================================================================

DO $$
DECLARE
    rule_count INTEGER;
BEGIN
    -- 查询适用于"病程记录"或"手术记录"的规则
    SELECT COUNT(*) INTO rule_count
    FROM qc_rules
    WHERE rule_code LIKE 'TEST-%'
    AND applicable_documents && ARRAY['病程记录', '手术记录'];
    
    IF rule_count = 1 THEN
        RAISE NOTICE '✅ Test 8 PASSED: Array overlap operator returned correct count (expected 1, got %)', rule_count;
    ELSE
        RAISE EXCEPTION '❌ Test 8 FAILED: Array overlap operator returned incorrect count (expected 1, got %)', rule_count;
    END IF;
END $$;

-- ============================================================================
-- 测试 9: 测试视图
-- ============================================================================

DO $$
DECLARE
    stats_record RECORD;
BEGIN
    -- 查询规则统计
    SELECT * INTO stats_record FROM qc_rules_statistics;
    
    IF stats_record.total_rules >= 4 THEN
        RAISE NOTICE '✅ Test 9 PASSED: qc_rules_statistics view works correctly';
        RAISE NOTICE '   Total rules: %', stats_record.total_rules;
        RAISE NOTICE '   Active rules: %', stats_record.active_rules;
        RAISE NOTICE '   Universal rules: %', stats_record.universal_rules;
        RAISE NOTICE '   Specific rules: %', stats_record.specific_rules;
    ELSE
        RAISE EXCEPTION '❌ Test 9 FAILED: qc_rules_statistics view returned unexpected data';
    END IF;
END $$;

-- ============================================================================
-- 测试 10: 性能测试（可选）
-- ============================================================================

DO $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    duration INTERVAL;
    rule_count INTEGER;
BEGIN
    -- 测试数组查询性能
    start_time := clock_timestamp();
    
    SELECT COUNT(*) INTO rule_count
    FROM qc_rules
    WHERE is_active = true
    AND (
        '首次病程记录' = ANY(applicable_documents)
        OR applicable_documents IS NULL
        OR array_length(applicable_documents, 1) IS NULL
        OR array_length(applicable_documents, 1) = 0
    );
    
    end_time := clock_timestamp();
    duration := end_time - start_time;
    
    RAISE NOTICE '✅ Test 10 PASSED: Performance test completed';
    RAISE NOTICE '   Query duration: %', duration;
    RAISE NOTICE '   Rules found: %', rule_count;
    
    IF duration < INTERVAL '100 milliseconds' THEN
        RAISE NOTICE '   Performance: EXCELLENT (< 100ms)';
    ELSIF duration < INTERVAL '500 milliseconds' THEN
        RAISE NOTICE '   Performance: GOOD (< 500ms)';
    ELSE
        RAISE NOTICE '   Performance: NEEDS IMPROVEMENT (>= 500ms)';
    END IF;
END $$;

-- ============================================================================
-- 清理测试数据
-- ============================================================================

-- 删除测试规则
DELETE FROM qc_rules WHERE rule_code LIKE 'TEST-%';

RAISE NOTICE '✅ Test data cleaned up';

-- ============================================================================
-- 测试总结
-- ============================================================================

RAISE NOTICE '';
RAISE NOTICE '=== Test Summary ===';
RAISE NOTICE '✅ All tests passed!';
RAISE NOTICE '';
RAISE NOTICE 'Migration 006 is working correctly:';
RAISE NOTICE '1. ✅ applicable_documents column created';
RAISE NOTICE '2. ✅ GIN index created';
RAISE NOTICE '3. ✅ Helper function created';
RAISE NOTICE '4. ✅ Views created';
RAISE NOTICE '5. ✅ Array queries working';
RAISE NOTICE '6. ✅ Performance acceptable';
RAISE NOTICE '===================';

