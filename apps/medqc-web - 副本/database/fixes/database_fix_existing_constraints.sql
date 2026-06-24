-- =============================================
-- 修复已存在表的约束问题
-- 解决 analytics_metrics 表约束冲突
-- =============================================

-- 第一步：检查当前状态
DO $$
BEGIN
    RAISE NOTICE '=== 检查当前数据库状态 ===';
    
    -- 检查表是否存在
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analytics_metrics') THEN
        RAISE NOTICE '✅ analytics_metrics 表已存在';
    ELSE
        RAISE NOTICE '❌ analytics_metrics 表不存在';
    END IF;
    
    -- 检查当前约束
    IF EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'analytics_metrics_category_check'
    ) THEN
        RAISE NOTICE '⚠️  发现旧的 category 约束';
    END IF;
    
    -- 检查当前数据
    DECLARE
        record_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO record_count FROM analytics_metrics;
        RAISE NOTICE '📊 当前记录数: %', record_count;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '❌ 无法查询 analytics_metrics 表';
    END;
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

-- 第四步：清理可能的冲突数据
DELETE FROM analytics_metrics WHERE 
    category NOT IN ('quality', 'performance', 'usage', 'cost', 'compliance', 'timeliness', 'accuracy', 'efficiency', 'productivity', 'volume')
    OR metric_type NOT IN ('count', 'percentage', 'average', 'sum', 'ratio', 'rate', 'trend');

-- 第五步：添加唯一约束（如果不存在）
DO $$
BEGIN
    -- 检查是否已有 metric_name 唯一约束
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'analytics_metrics_metric_name_key'
        AND table_name = 'analytics_metrics'
    ) THEN
        -- 先删除可能的重复数据
        DELETE FROM analytics_metrics a1 USING analytics_metrics a2
        WHERE a1.id > a2.id AND a1.metric_name = a2.metric_name;

        -- 添加唯一约束
        ALTER TABLE analytics_metrics ADD CONSTRAINT analytics_metrics_metric_name_key UNIQUE (metric_name);
        RAISE NOTICE '✅ 添加 metric_name 唯一约束';
    ELSE
        RAISE NOTICE '⚠️  metric_name 唯一约束已存在';
    END IF;
END $$;

-- 第六步：插入或更新分析指标数据
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
    target_value = EXCLUDED.target_value;

-- 第七步：处理其他可能存在的表
-- 如果 report_templates 表已存在但缺少外键，先创建一个临时的 created_by
DO $$
BEGIN
    -- 检查 report_templates 表是否存在
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'report_templates') THEN
        RAISE NOTICE '⚠️  report_templates 表已存在，跳过创建';
    ELSE
        -- 创建 report_templates 表
        CREATE TABLE report_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_name VARCHAR(200) NOT NULL,
            template_type VARCHAR(50) NOT NULL
                CHECK (template_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual', 'custom')),
            description TEXT,
            template_config JSONB NOT NULL DEFAULT '{}',
            chart_configs JSONB DEFAULT '[]',
            filter_options JSONB DEFAULT '{}',
            export_formats TEXT[] DEFAULT ARRAY['pdf', 'excel'],
            is_public BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            created_by UUID, -- 暂时允许 NULL，稍后添加外键
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        RAISE NOTICE '✅ report_templates 表创建成功';
    END IF;
END $$;

-- 第八步：处理 data_snapshots 表
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'data_snapshots') THEN
        RAISE NOTICE '⚠️  data_snapshots 表已存在，跳过创建';
    ELSE
        CREATE TABLE data_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date DATE NOT NULL,
            snapshot_type VARCHAR(50) NOT NULL
                CHECK (snapshot_type IN ('daily', 'weekly', 'monthly')),
            department_id UUID REFERENCES departments(id),
            metrics_data JSONB NOT NULL DEFAULT '{}',
            summary_stats JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            CONSTRAINT unique_snapshot UNIQUE (snapshot_date, snapshot_type, department_id)
        );
        RAISE NOTICE '✅ data_snapshots 表创建成功';
    END IF;
END $$;

-- 第九步：创建缺失的索引（如果不存在）
DO $$
BEGIN
    -- 为 analytics_metrics 创建索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_analytics_metrics_category') THEN
        CREATE INDEX idx_analytics_metrics_category ON analytics_metrics(category);
        RAISE NOTICE '✅ 创建 analytics_metrics category 索引';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_analytics_metrics_type') THEN
        CREATE INDEX idx_analytics_metrics_type ON analytics_metrics(metric_type);
        RAISE NOTICE '✅ 创建 analytics_metrics metric_type 索引';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_analytics_metrics_active') THEN
        CREATE INDEX idx_analytics_metrics_active ON analytics_metrics(is_active);
        RAISE NOTICE '✅ 创建 analytics_metrics is_active 索引';
    END IF;
END $$;

-- 第十步：验证修复结果
DO $$
BEGIN
    RAISE NOTICE '=== 修复结果验证 ===';
    
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
    
    RAISE NOTICE '=== 验证完成 ===';
END $$;

-- 第十一步：显示最终结果
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
