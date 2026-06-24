-- =============================================
-- 完成数据库设置脚本
-- 补充缺失的策略、数据等
-- =============================================

-- 第一步：检查当前状态
DO $$
BEGIN
    RAISE NOTICE '=== 检查当前数据库状态 ===';
    
    -- 检查科室数据
    DECLARE
        dept_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO dept_count FROM departments;
        RAISE NOTICE '📊 科室数据: % 条记录', dept_count;
    END;
    
    -- 检查分析指标数据
    DECLARE
        metrics_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO metrics_count FROM analytics_metrics;
        RAISE NOTICE '📊 分析指标数据: % 条记录', metrics_count;
    END;
    
    -- 检查RLS策略数量
    DECLARE
        policies_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO policies_count FROM pg_policies WHERE schemaname = 'public';
        RAISE NOTICE '🔒 RLS策略数量: % 个', policies_count;
    END;
END $$;

-- 第二步：确保科室数据完整
INSERT INTO departments (name, code, description, category) VALUES
('内科', 'INTERNAL', '内科系统，包括心内科、呼吸内科、消化内科等', 'clinical'),
('外科', 'SURGERY', '外科系统，包括普外科、骨科、神经外科等', 'surgical'),
('儿科', 'PEDIATRIC', '儿童医学科室', 'pediatric'),
('妇产科', 'OBSTETRICS', '妇科和产科', 'obstetrics'),
('急诊科', 'EMERGENCY', '急诊医学科', 'emergency'),
('ICU', 'ICU', '重症监护科', 'icu'),
('病理科', 'PATHOLOGY', '病理诊断科', 'diagnostic'),
('放射科', 'RADIOLOGY', '医学影像科', 'diagnostic'),
('检验科', 'LABORATORY', '临床检验科', 'diagnostic'),
('药剂科', 'PHARMACY', '药学服务科', 'clinical')
ON CONFLICT (name) DO NOTHING;

-- 第三步：确保分析指标数据完整
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
ON CONFLICT DO NOTHING;

-- 第四步：补充缺失的RLS策略
-- 医疗记录策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '医生可以创建医疗记录' AND tablename = 'medical_records') THEN
        CREATE POLICY "医生可以创建医疗记录" ON medical_records
            FOR INSERT WITH CHECK (
                EXISTS (
                    SELECT 1 FROM user_profiles 
                    WHERE user_id = auth.uid() 
                    AND role_type IN ('doctor', 'admin')
                )
            );
        RAISE NOTICE '✅ 创建医疗记录插入策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '医生可以更新自己创建的记录' AND tablename = 'medical_records') THEN
        CREATE POLICY "医生可以更新自己创建的记录" ON medical_records
            FOR UPDATE USING (
                created_by = (
                    SELECT id FROM user_profiles WHERE user_id = auth.uid()
                )
            );
        RAISE NOTICE '✅ 创建医疗记录更新策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建医疗记录策略时出错: %', SQLERRM;
END $$;

-- 质控规则策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '所有认证用户可以查看激活的质控规则' AND tablename = 'qc_rules') THEN
        CREATE POLICY "所有认证用户可以查看激活的质控规则" ON qc_rules
            FOR SELECT USING (is_active = true AND auth.role() = 'authenticated');
        RAISE NOTICE '✅ 创建质控规则查看策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '质控管理员可以管理规则' AND tablename = 'qc_rules') THEN
        CREATE POLICY "质控管理员可以管理规则" ON qc_rules
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM user_profiles 
                    WHERE user_id = auth.uid() 
                    AND role_type IN ('admin', 'qc_manager')
                )
            );
        RAISE NOTICE '✅ 创建质控规则管理策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建质控规则策略时出错: %', SQLERRM;
END $$;

-- 质控结果策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以查看相关的质控结果' AND tablename = 'qc_results') THEN
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
        RAISE NOTICE '✅ 创建质控结果查看策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建质控结果策略时出错: %', SQLERRM;
END $$;

-- 批量任务策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以查看自己创建的任务' AND tablename = 'batch_processing_tasks') THEN
        CREATE POLICY "用户可以查看自己创建的任务" ON batch_processing_tasks
            FOR SELECT USING (
                created_by = (
                    SELECT id FROM user_profiles WHERE user_id = auth.uid()
                )
            );
        RAISE NOTICE '✅ 创建批量任务查看策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以创建批量任务' AND tablename = 'batch_processing_tasks') THEN
        CREATE POLICY "用户可以创建批量任务" ON batch_processing_tasks
            FOR INSERT WITH CHECK (
                created_by = (
                    SELECT id FROM user_profiles WHERE user_id = auth.uid()
                )
            );
        RAISE NOTICE '✅ 创建批量任务插入策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建批量任务策略时出错: %', SQLERRM;
END $$;

-- 告警记录策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以查看相关告警' AND tablename = 'alert_records') THEN
        CREATE POLICY "用户可以查看相关告警" ON alert_records
            FOR SELECT USING (
                related_user_id = (
                    SELECT id FROM user_profiles WHERE user_id = auth.uid()
                )
                OR EXISTS (
                    SELECT 1 FROM user_profiles 
                    WHERE user_id = auth.uid() 
                    AND role_type IN ('admin', 'qc_manager')
                )
            );
        RAISE NOTICE '✅ 创建告警记录查看策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建告警记录策略时出错: %', SQLERRM;
END $$;

-- 第五步：创建缺失的视图（如果不存在）
DO $$
BEGIN
    -- 检查并创建科室质控统计视图
    IF NOT EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_department_qc_stats') THEN
        CREATE VIEW v_department_qc_stats AS
        SELECT 
            d.id as department_id,
            d.name as department_name,
            d.code as department_code,
            COUNT(mr.id) as total_records,
            COUNT(CASE WHEN mr.status = 'completed' THEN 1 END) as completed_records,
            COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
            COUNT(CASE WHEN mr.qc_grade = '乙级' THEN 1 END) as grade_b_count,
            COUNT(CASE WHEN mr.qc_grade = '丙级' THEN 1 END) as grade_c_count,
            ROUND(AVG(mr.qc_score), 2) as avg_qc_score,
            COUNT(CASE WHEN mr.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as records_last_30_days
        FROM departments d
        LEFT JOIN medical_records mr ON d.id = mr.department_id
        WHERE d.is_active = true
        GROUP BY d.id, d.name, d.code;
        RAISE NOTICE '✅ 创建科室质控统计视图';
    END IF;
    
    -- 检查并创建医生表现视图
    IF NOT EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_doctor_performance') THEN
        CREATE VIEW v_doctor_performance AS
        SELECT 
            up.id as doctor_id,
            up.full_name as doctor_name,
            up.department_id,
            d.name as department_name,
            COUNT(mr.id) as total_records,
            COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
            ROUND(
                COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) * 100.0 / NULLIF(COUNT(mr.id), 0), 
                2
            ) as grade_a_rate,
            ROUND(AVG(mr.qc_score), 2) as avg_qc_score,
            COUNT(CASE WHEN mr.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as records_last_30_days
        FROM user_profiles up
        LEFT JOIN medical_records mr ON up.id = mr.doctor_id
        LEFT JOIN departments d ON up.department_id = d.id
        WHERE up.role_type = 'doctor' AND up.is_active = true
        GROUP BY up.id, up.full_name, up.department_id, d.name;
        RAISE NOTICE '✅ 创建医生表现视图';
    END IF;
    
    -- 检查并创建质控趋势视图
    IF NOT EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_qc_trends') THEN
        CREATE VIEW v_qc_trends AS
        SELECT 
            DATE(mr.created_at) as analysis_date,
            COUNT(mr.id) as total_records,
            COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
            COUNT(CASE WHEN mr.qc_grade = '乙级' THEN 1 END) as grade_b_count,
            COUNT(CASE WHEN mr.qc_grade = '丙级' THEN 1 END) as grade_c_count,
            ROUND(AVG(mr.qc_score), 2) as avg_score,
            COUNT(CASE WHEN qr.result_status = 'failed' THEN 1 END) as total_issues
        FROM medical_records mr
        LEFT JOIN qc_results qr ON mr.id = qr.record_id
        WHERE mr.status = 'completed'
        GROUP BY DATE(mr.created_at)
        ORDER BY analysis_date DESC;
        RAISE NOTICE '✅ 创建质控趋势视图';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建视图时出错: %', SQLERRM;
END $$;

-- 第六步：最终验证
DO $$
BEGIN
    RAISE NOTICE '=== 最终验证结果 ===';
    
    -- 检查科室数据
    DECLARE
        dept_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO dept_count FROM departments;
        RAISE NOTICE '✅ 科室数据: % 条记录', dept_count;
    END;
    
    -- 检查分析指标数据
    DECLARE
        metrics_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO metrics_count FROM analytics_metrics;
        RAISE NOTICE '✅ 分析指标数据: % 条记录', metrics_count;
    END;
    
    -- 检查RLS策略数量
    DECLARE
        policies_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO policies_count FROM pg_policies WHERE schemaname = 'public';
        RAISE NOTICE '✅ RLS策略数量: % 个', policies_count;
    END;
    
    -- 检查视图数量
    DECLARE
        views_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO views_count FROM pg_views WHERE schemaname = 'public';
        RAISE NOTICE '✅ 视图数量: % 个', views_count;
    END;
    
    RAISE NOTICE '=== 补充设置完成 ===';
END $$;
