-- =============================================
-- 医疗质控系统数据库初始化脚本 - 第三部分
-- 版本: 2.0.0 (全新设计)
-- 创建时间: 2024-12-25
-- 新 Supabase 项目: https://dgsdkdbjpucyawnyfbdu.supabase.co
-- =============================================

-- =============================================
-- 第八步：RLS 安全策略
-- =============================================

-- 启用 RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_processing_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_records ENABLE ROW LEVEL SECURITY;

-- 用户档案策略
CREATE POLICY "用户可以查看自己的档案" ON user_profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "用户可以更新自己的档案" ON user_profiles
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "管理员可以查看所有用户档案" ON user_profiles
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() AND role_type = 'admin'
        )
    );

-- 科室策略
CREATE POLICY "所有认证用户可以查看科室信息" ON departments
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "管理员可以管理科室" ON departments
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() AND role_type = 'admin'
        )
    );

-- 医疗记录策略
CREATE POLICY "用户可以查看本科室的医疗记录" ON medical_records
    FOR SELECT USING (
        department_id IN (
            SELECT department_id FROM user_profiles 
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "医生可以创建医疗记录" ON medical_records
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() 
            AND role_type IN ('doctor', 'admin')
        )
    );

CREATE POLICY "医生可以更新自己创建的记录" ON medical_records
    FOR UPDATE USING (
        created_by = (
            SELECT id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

-- 质控规则策略
CREATE POLICY "所有认证用户可以查看激活的质控规则" ON qc_rules
    FOR SELECT USING (is_active = true AND auth.role() = 'authenticated');

CREATE POLICY "质控管理员可以管理规则" ON qc_rules
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() 
            AND role_type IN ('admin', 'qc_manager')
        )
    );

-- 质控结果策略
CREATE POLICY "用户可以查看相关的质控结果" ON qc_results
    FOR SELECT USING (
        record_id IN (
            SELECT id FROM medical_records 
            WHERE department_id IN (
                SELECT department_id FROM user_profiles 
                WHERE user_id = auth.uid()
            )
        )
    );

-- 批量任务策略
CREATE POLICY "用户可以查看自己创建的任务" ON batch_processing_tasks
    FOR SELECT USING (
        created_by = (
            SELECT id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "用户可以创建批量任务" ON batch_processing_tasks
    FOR INSERT WITH CHECK (
        created_by = (
            SELECT id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

-- =============================================
-- 第九步：创建函数和触发器
-- =============================================

-- 更新时间戳函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表添加更新时间戳触发器
CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_departments_updated_at BEFORE UPDATE ON departments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_medical_records_updated_at BEFORE UPDATE ON medical_records FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_qc_rules_updated_at BEFORE UPDATE ON qc_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_report_templates_updated_at BEFORE UPDATE ON report_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 计算医疗记录字数函数
CREATE OR REPLACE FUNCTION calculate_word_count()
RETURNS TRIGGER AS $$
BEGIN
    NEW.word_count = LENGTH(REPLACE(NEW.content, ' ', ''));
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER calculate_medical_record_word_count 
    BEFORE INSERT OR UPDATE ON medical_records 
    FOR EACH ROW EXECUTE FUNCTION calculate_word_count();

-- 自动清理过期缓存函数
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM qc_analysis_cache WHERE expires_at < NOW();
END;
$$ language 'plpgsql';

-- =============================================
-- 第十步：插入初始化数据
-- =============================================

-- 插入默认科室
INSERT INTO departments (name, code, description, category) VALUES
('内科', 'INTERNAL', '内科系统，包括心内科、呼吸内科、消化内科等', 'clinical'),
('外科', 'SURGERY', '外科系统，包括普外科、骨科、神经外科等', 'surgical'),
('儿科', 'PEDIATRIC', '儿童医学科室', 'pediatric'),
('妇产科', 'OBSTETRICS', '妇科和产科', 'obstetrics'),
('急诊科', 'EMERGENCY', '急诊医学科', 'emergency'),
('ICU', 'ICU', '重症监护科', 'icu'),
('病理科', 'PATHOLOGY', '病理诊断科', 'diagnostic');

-- 插入分析指标
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

-- 插入报告模板（需要先有用户档案，这里使用占位符）
-- INSERT INTO report_templates (template_name, template_type, description, template_config, created_by) VALUES
-- ('日报模板', 'daily', '每日质控统计报告', '{"sections": ["summary", "department_stats", "issues"], "charts": ["trend", "distribution"]}', '00000000-0000-0000-0000-000000000000'),
-- ('月报模板', 'monthly', '月度质控分析报告', '{"sections": ["overview", "trends", "department_comparison", "recommendations"], "charts": ["monthly_trend", "department_ranking", "issue_categories"]}', '00000000-0000-0000-0000-000000000000'),
-- ('科室专项报告', 'custom', '针对特定科室的专项质控报告', '{"sections": ["department_overview", "doctor_performance", "common_issues"], "filters": ["department", "date_range"]}', '00000000-0000-0000-0000-000000000000');

-- =============================================
-- 验证脚本
-- =============================================

-- 检查表创建情况
SELECT 
    'Tables Created' as check_type,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
AND table_name NOT LIKE 'pg_%'
AND table_name NOT LIKE 'sql_%';

-- 检查索引创建情况
SELECT 
    'Indexes Created' as check_type,
    COUNT(*) as count
FROM pg_indexes 
WHERE schemaname = 'public'
AND indexname NOT LIKE 'pg_%';

-- 检查视图创建情况
SELECT 
    'Views Created' as check_type,
    COUNT(*) as count
FROM pg_views 
WHERE schemaname = 'public';

-- 检查初始数据
SELECT 
    'Departments' as data_type,
    COUNT(*) as count
FROM departments
UNION ALL
SELECT 
    'Analytics Metrics' as data_type,
    COUNT(*) as count
FROM analytics_metrics;

-- 显示所有创建的表
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
AND table_name NOT LIKE 'pg_%'
AND table_name NOT LIKE 'sql_%'
ORDER BY table_name;
