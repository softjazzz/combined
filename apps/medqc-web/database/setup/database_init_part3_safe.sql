-- =============================================
-- 医疗质控系统数据库初始化脚本 - 第三部分（安全版本）
-- 版本: 2.0.0 (全新设计)
-- 创建时间: 2024-12-25
-- 说明: 跳过已存在的表，只执行必要的操作
-- =============================================

-- =============================================
-- 第八步：RLS 安全策略
-- =============================================

-- 启用 RLS（如果表存在）
DO $$
BEGIN
    -- 检查并启用 RLS
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'user_profiles') THEN
        ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ user_profiles RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'departments') THEN
        ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ departments RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'medical_records') THEN
        ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ medical_records RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'qc_rules') THEN
        ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ qc_rules RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'qc_results') THEN
        ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ qc_results RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'batch_processing_tasks') THEN
        ALTER TABLE batch_processing_tasks ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ batch_processing_tasks RLS 已启用';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'alert_records') THEN
        ALTER TABLE alert_records ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ alert_records RLS 已启用';
    END IF;
END $$;

-- 创建 RLS 策略（如果不存在）
-- 用户档案策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以查看自己的档案' AND tablename = 'user_profiles') THEN
        CREATE POLICY "用户可以查看自己的档案" ON user_profiles
            FOR SELECT USING (auth.uid() = user_id);
        RAISE NOTICE '✅ 创建用户档案查看策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以更新自己的档案' AND tablename = 'user_profiles') THEN
        CREATE POLICY "用户可以更新自己的档案" ON user_profiles
            FOR UPDATE USING (auth.uid() = user_id);
        RAISE NOTICE '✅ 创建用户档案更新策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '管理员可以查看所有用户档案' AND tablename = 'user_profiles') THEN
        CREATE POLICY "管理员可以查看所有用户档案" ON user_profiles
            FOR SELECT USING (
                EXISTS (
                    SELECT 1 FROM user_profiles 
                    WHERE user_id = auth.uid() AND role_type = 'admin'
                )
            );
        RAISE NOTICE '✅ 创建管理员用户档案策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建用户档案策略时出错: %', SQLERRM;
END $$;

-- 科室策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '所有认证用户可以查看科室信息' AND tablename = 'departments') THEN
        CREATE POLICY "所有认证用户可以查看科室信息" ON departments
            FOR SELECT USING (auth.role() = 'authenticated');
        RAISE NOTICE '✅ 创建科室查看策略';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '管理员可以管理科室' AND tablename = 'departments') THEN
        CREATE POLICY "管理员可以管理科室" ON departments
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM user_profiles 
                    WHERE user_id = auth.uid() AND role_type = 'admin'
                )
            );
        RAISE NOTICE '✅ 创建科室管理策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建科室策略时出错: %', SQLERRM;
END $$;

-- 医疗记录策略
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = '用户可以查看本科室的医疗记录' AND tablename = 'medical_records') THEN
        CREATE POLICY "用户可以查看本科室的医疗记录" ON medical_records
            FOR SELECT USING (
                department_id IN (
                    SELECT department_id FROM user_profiles 
                    WHERE user_id = auth.uid()
                )
            );
        RAISE NOTICE '✅ 创建医疗记录查看策略';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '⚠️  创建医疗记录策略时出错: %', SQLERRM;
END $$;

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

-- 为需要的表添加更新时间戳触发器（如果表存在且触发器不存在）
DO $$
BEGIN
    -- user_profiles 触发器
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'user_profiles') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_user_profiles_updated_at') THEN
        CREATE TRIGGER update_user_profiles_updated_at 
            BEFORE UPDATE ON user_profiles 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '✅ 创建 user_profiles 更新触发器';
    END IF;
    
    -- departments 触发器
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'departments') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_departments_updated_at') THEN
        CREATE TRIGGER update_departments_updated_at 
            BEFORE UPDATE ON departments 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '✅ 创建 departments 更新触发器';
    END IF;
    
    -- medical_records 触发器
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'medical_records') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_medical_records_updated_at') THEN
        CREATE TRIGGER update_medical_records_updated_at 
            BEFORE UPDATE ON medical_records 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '✅ 创建 medical_records 更新触发器';
    END IF;
    
    -- qc_rules 触发器
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'qc_rules') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_qc_rules_updated_at') THEN
        CREATE TRIGGER update_qc_rules_updated_at 
            BEFORE UPDATE ON qc_rules 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '✅ 创建 qc_rules 更新触发器';
    END IF;
    
    -- report_templates 触发器
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'report_templates') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_report_templates_updated_at') THEN
        CREATE TRIGGER update_report_templates_updated_at 
            BEFORE UPDATE ON report_templates 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE '✅ 创建 report_templates 更新触发器';
    END IF;
END $$;

-- 计算医疗记录字数函数
CREATE OR REPLACE FUNCTION calculate_word_count()
RETURNS TRIGGER AS $$
BEGIN
    NEW.word_count = LENGTH(REPLACE(NEW.content, ' ', ''));
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为 medical_records 创建字数计算触发器
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'medical_records') 
       AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'calculate_medical_record_word_count') THEN
        CREATE TRIGGER calculate_medical_record_word_count 
            BEFORE INSERT OR UPDATE ON medical_records 
            FOR EACH ROW EXECUTE FUNCTION calculate_word_count();
        RAISE NOTICE '✅ 创建 medical_records 字数计算触发器';
    END IF;
END $$;

-- 自动清理过期缓存函数
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'qc_analysis_cache') THEN
        DELETE FROM qc_analysis_cache WHERE expires_at < NOW();
    END IF;
END;
$$ language 'plpgsql';

-- =============================================
-- 第十步：插入初始化数据（如果不存在）
-- =============================================

-- 插入默认科室（如果不存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'departments') THEN
        INSERT INTO departments (name, code, description, category) VALUES
        ('内科', 'INTERNAL', '内科系统，包括心内科、呼吸内科、消化内科等', 'clinical'),
        ('外科', 'SURGERY', '外科系统，包括普外科、骨科、神经外科等', 'surgical'),
        ('儿科', 'PEDIATRIC', '儿童医学科室', 'pediatric'),
        ('妇产科', 'OBSTETRICS', '妇科和产科', 'obstetrics'),
        ('急诊科', 'EMERGENCY', '急诊医学科', 'emergency'),
        ('ICU', 'ICU', '重症监护科', 'icu'),
        ('病理科', 'PATHOLOGY', '病理诊断科', 'diagnostic')
        ON CONFLICT (name) DO NOTHING;
        
        RAISE NOTICE '✅ 科室数据插入完成';
    END IF;
END $$;

-- 验证最终状态
DO $$
BEGIN
    RAISE NOTICE '=== 数据库初始化验证 ===';
    
    -- 检查科室数据
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'departments') THEN
        DECLARE
            dept_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO dept_count FROM departments;
            RAISE NOTICE '✅ 科室数据: % 条记录', dept_count;
        END;
    END IF;
    
    -- 检查分析指标数据
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analytics_metrics') THEN
        DECLARE
            metrics_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO metrics_count FROM analytics_metrics;
            RAISE NOTICE '✅ 分析指标数据: % 条记录', metrics_count;
        END;
    END IF;
    
    RAISE NOTICE '=== 初始化完成 ===';
END $$;
