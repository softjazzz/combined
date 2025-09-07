-- =============================================
-- 修复 analytics_metrics 表约束问题
-- 解决 category 字段约束不匹配的问题
-- =============================================

-- 1. 删除现有的约束
ALTER TABLE analytics_metrics DROP CONSTRAINT IF EXISTS analytics_metrics_category_check;

-- 2. 添加更完整的约束，包含所有需要的类别
ALTER TABLE analytics_metrics ADD CONSTRAINT analytics_metrics_category_check 
CHECK (category IN ('quality', 'performance', 'usage', 'cost', 'compliance', 'timeliness', 'accuracy', 'efficiency', 'productivity', 'volume'));

-- 3. 同样修复 metric_type 约束（如果需要）
ALTER TABLE analytics_metrics DROP CONSTRAINT IF EXISTS analytics_metrics_metric_type_check;
ALTER TABLE analytics_metrics ADD CONSTRAINT analytics_metrics_metric_type_check 
CHECK (metric_type IN ('count', 'percentage', 'average', 'sum', 'ratio', 'trend', 'rate'));

-- 4. 清理可能存在的错误数据
DELETE FROM analytics_metrics WHERE category NOT IN ('quality', 'performance', 'usage', 'cost', 'compliance', 'timeliness', 'accuracy', 'efficiency', 'productivity', 'volume');

-- 5. 重新插入正确的分析指标数据
INSERT INTO analytics_metrics (metric_name, metric_type, category, description, unit, target_value) VALUES
('甲级病历率', 'percentage', 'quality', '甲级病历占总病历的百分比', '%', 90.00),
('平均质控得分', 'average', 'quality', '所有病历的平均质控得分', '分', 85.00),
('病历完成及时率', 'percentage', 'timeliness', '按时完成病历的百分比', '%', 95.00),
('质控问题发现率', 'percentage', 'performance', '发现质控问题的病历比例', '%', 15.00),
('人工复核准确率', 'percentage', 'accuracy', '人工复核结果的准确率', '%', 98.00),
('平均处理时间', 'average', 'efficiency', '单个病历的平均处理时间', '分钟', 30.00),
('医生工作效率', 'rate', 'productivity', '医生每日处理病历数量', '份/日', 20.00),
('系统响应时间', 'average', 'performance', '系统平均响应时间', '秒', 2.00),
('数据完整性', 'percentage', 'quality', '病历数据完整性比例', '%', 95.00),
('用户满意度', 'percentage', 'usage', '用户满意度评分', '%', 85.00)
ON CONFLICT (metric_name) DO UPDATE SET
    metric_type = EXCLUDED.metric_type,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    unit = EXCLUDED.unit,
    target_value = EXCLUDED.target_value,
    updated_at = NOW();

-- 6. 验证修复结果
DO $$
BEGIN
    RAISE NOTICE '=== 约束修复验证 ===';
    
    -- 检查约束是否正确创建
    IF EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'analytics_metrics_category_check'
        AND check_clause LIKE '%timeliness%'
    ) THEN
        RAISE NOTICE '✅ category 约束已正确更新';
    ELSE
        RAISE NOTICE '❌ category 约束更新失败';
    END IF;
    
    -- 检查数据插入情况
    DECLARE
        record_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO record_count FROM analytics_metrics;
        RAISE NOTICE '✅ 分析指标数据: % 条记录', record_count;
    END;
    
    -- 显示所有类别
    DECLARE
        categories TEXT;
    BEGIN
        SELECT string_agg(DISTINCT category, ', ' ORDER BY category) INTO categories 
        FROM analytics_metrics;
        RAISE NOTICE '📊 当前类别: %', categories;
    END;
    
    RAISE NOTICE '=== 验证完成 ===';
END $$;

-- 7. 显示修复后的数据
SELECT 
    metric_name,
    metric_type,
    category,
    unit,
    target_value,
    is_active
FROM analytics_metrics 
ORDER BY category, metric_name;
