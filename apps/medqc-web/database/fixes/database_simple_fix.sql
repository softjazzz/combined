-- =============================================
-- 简单修复脚本 - 解决约束问题
-- 避免复杂的 ON CONFLICT 操作
-- =============================================

-- 第一步：检查当前状态
DO $$
BEGIN
    RAISE NOTICE '=== 开始修复约束问题 ===';
    
    -- 检查表是否存在
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analytics_metrics') THEN
        RAISE NOTICE '✅ analytics_metrics 表已存在';
        
        -- 检查当前数据
        DECLARE
            record_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO record_count FROM analytics_metrics;
            RAISE NOTICE '📊 当前记录数: %', record_count;
        END;
    ELSE
        RAISE NOTICE '❌ analytics_metrics 表不存在';
    END IF;
END $$;

-- 第二步：删除旧约束
ALTER TABLE analytics_metrics DROP CONSTRAINT IF EXISTS analytics_metrics_category_check;
ALTER TABLE analytics_metrics DROP CONSTRAINT IF EXISTS analytics_metrics_metric_type_check;

-- 第三步：添加新约束
ALTER TABLE analytics_metrics ADD CONSTRAINT analytics_metrics_category_check 
CHECK (category IN (
    'quality', 'performance', 'usage', 'cost', 'compliance', 
    'timeliness', 'accuracy', 'efficiency', 'productivity', 'volume'
));

ALTER TABLE analytics_metrics ADD CONSTRAINT analytics_metrics_metric_type_check 
CHECK (metric_type IN (
    'count', 'percentage', 'average', 'sum', 'ratio', 'rate', 'trend'
));

-- 第四步：清理现有数据
DELETE FROM analytics_metrics;

-- 第五步：插入新数据（简单插入，不使用 ON CONFLICT）
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
('用户满意度', 'percentage', 'usage', '用户满意度评分', '%', 85.00);

-- 第六步：验证结果
DO $$
BEGIN
    RAISE NOTICE '=== 验证修复结果 ===';
    
    -- 检查约束
    IF EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'analytics_metrics_category_check'
        AND check_clause LIKE '%timeliness%'
    ) THEN
        RAISE NOTICE '✅ category 约束已正确更新';
    ELSE
        RAISE NOTICE '❌ category 约束更新失败';
    END IF;
    
    -- 检查数据
    DECLARE
        record_count INTEGER;
        categories TEXT;
    BEGIN
        SELECT COUNT(*) INTO record_count FROM analytics_metrics;
        RAISE NOTICE '✅ 分析指标数据: % 条记录', record_count;
        
        SELECT string_agg(DISTINCT category, ', ' ORDER BY category) INTO categories 
        FROM analytics_metrics;
        RAISE NOTICE '📊 当前类别: %', categories;
    END;
    
    -- 测试插入一条 timeliness 类别的数据
    BEGIN
        INSERT INTO analytics_metrics (metric_name, metric_type, category, description) 
        VALUES ('测试及时性指标', 'percentage', 'timeliness', '测试约束是否正常');
        
        DELETE FROM analytics_metrics WHERE metric_name = '测试及时性指标';
        RAISE NOTICE '✅ timeliness 类别约束测试通过';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '❌ timeliness 类别约束测试失败: %', SQLERRM;
    END;
    
    RAISE NOTICE '=== 修复完成 ===';
END $$;

-- 第七步：显示最终结果
SELECT 
    '修复完成' as status,
    COUNT(*) as total_metrics,
    COUNT(DISTINCT category) as categories_count,
    COUNT(DISTINCT metric_type) as types_count
FROM analytics_metrics;

-- 显示所有指标
SELECT 
    metric_name,
    metric_type,
    category,
    unit,
    target_value,
    is_active
FROM analytics_metrics 
ORDER BY category, metric_name;
