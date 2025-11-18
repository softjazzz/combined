-- ============================================================================
-- 迁移 007 预检查脚本
-- 描述: 在执行迁移 007 之前，检查数据库状态
-- 日期: 2025-10-12
-- ============================================================================

-- 检查所需的表是否存在
DO $$
DECLARE
  table_exists BOOLEAN;
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '开始检查数据库状态...';
  RAISE NOTICE '==============================================';
  
  -- 检查 medical_records 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'medical_records'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ medical_records 表存在';
  ELSE
    RAISE WARNING '❌ medical_records 表不存在！需要先执行 000_init_base_schema.sql';
  END IF;
  
  -- 检查 qc_rules 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'qc_rules'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ qc_rules 表存在';
  ELSE
    RAISE WARNING '❌ qc_rules 表不存在！需要先执行 000_init_base_schema.sql';
  END IF;
  
  -- 检查 qc_results 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'qc_results'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ qc_results 表存在';
  ELSE
    RAISE WARNING '❌ qc_results 表不存在！需要先执行 000_init_base_schema.sql';
  END IF;
  
  -- 检查 user_roles 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_roles'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ user_roles 表存在';
  ELSE
    RAISE NOTICE '⚠️  user_roles 表不存在（迁移 007 会自动创建）';
  END IF;
  
  RAISE NOTICE '==============================================';
  RAISE NOTICE '检查完成！';
  RAISE NOTICE '==============================================';
END $$;

-- 列出当前所有的表
SELECT 
  table_name,
  table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 列出当前所有的 RLS 策略
SELECT 
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

