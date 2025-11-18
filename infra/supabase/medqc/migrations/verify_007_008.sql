-- ============================================================================
-- 验证迁移 007 和 008
-- 描述: 验证权限系统迁移是否成功
-- 日期: 2025-10-12
-- ============================================================================

DO $$
DECLARE
  func_count INTEGER;
  policy_count INTEGER;
  table_exists BOOLEAN;
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '开始验证迁移 007 和 008...';
  RAISE NOTICE '==============================================';
  
  -- 1. 验证 user_roles 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_roles'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ user_roles 表已创建';
  ELSE
    RAISE WARNING '❌ user_roles 表不存在！';
  END IF;
  
  -- 2. 验证辅助函数
  SELECT COUNT(*) INTO func_count
  FROM pg_proc
  WHERE proname IN ('get_user_roles', 'has_role', 'has_any_role');
  
  IF func_count = 3 THEN
    RAISE NOTICE '✅ 辅助函数已创建 (3/3)';
  ELSE
    RAISE WARNING '❌ 辅助函数不完整 (%/3)', func_count;
  END IF;
  
  -- 3. 验证 RLS 策略
  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE tablename IN ('medical_records', 'qc_rules', 'qc_results', 'user_roles');
  
  IF policy_count = 16 THEN
    RAISE NOTICE '✅ RLS 策略已创建 (16/16)';
  ELSE
    RAISE WARNING '⚠️  RLS 策略数量: %/16', policy_count;
  END IF;
  
  -- 4. 验证 permission_audit_logs 表
  SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'permission_audit_logs'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ permission_audit_logs 表已创建';
  ELSE
    RAISE WARNING '❌ permission_audit_logs 表不存在！';
  END IF;
  
  -- 5. 验证审计日志视图
  SELECT EXISTS (
    SELECT FROM information_schema.views 
    WHERE table_schema = 'public' 
    AND table_name = 'permission_audit_summary'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ permission_audit_summary 视图已创建';
  ELSE
    RAISE WARNING '❌ permission_audit_summary 视图不存在！';
  END IF;
  
  -- 6. 验证清理函数
  SELECT EXISTS (
    SELECT FROM pg_proc 
    WHERE proname = 'cleanup_old_audit_logs'
  ) INTO table_exists;
  
  IF table_exists THEN
    RAISE NOTICE '✅ cleanup_old_audit_logs 函数已创建';
  ELSE
    RAISE WARNING '❌ cleanup_old_audit_logs 函数不存在！';
  END IF;
  
  RAISE NOTICE '==============================================';
  RAISE NOTICE '验证完成！';
  RAISE NOTICE '==============================================';
END $$;

-- 详细信息查询

-- 1. 列出所有辅助函数
SELECT 
  proname as function_name,
  pg_get_function_arguments(oid) as arguments,
  pg_get_function_result(oid) as return_type
FROM pg_proc
WHERE proname IN ('get_user_roles', 'has_role', 'has_any_role', 'cleanup_old_audit_logs')
ORDER BY proname;

-- 2. 列出所有 RLS 策略
SELECT 
  tablename,
  policyname,
  permissive,
  cmd as command
FROM pg_policies
WHERE tablename IN ('medical_records', 'qc_rules', 'qc_results', 'user_roles', 'permission_audit_logs')
ORDER BY tablename, policyname;

-- 3. 查看 user_roles 表结构
SELECT 
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_name = 'user_roles'
ORDER BY ordinal_position;

-- 4. 查看 permission_audit_logs 表结构
SELECT 
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_name = 'permission_audit_logs'
ORDER BY ordinal_position;

-- 5. 查看索引
SELECT 
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename IN ('user_roles', 'permission_audit_logs')
ORDER BY tablename, indexname;

