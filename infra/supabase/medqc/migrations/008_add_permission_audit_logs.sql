-- ============================================================================
-- 权限审计日志
-- 版本: 008
-- 描述: 创建权限审计日志表，记录所有权限检查操作
-- 日期: 2025-10-12
-- ============================================================================

-- 1. 创建权限审计日志表
CREATE TABLE IF NOT EXISTS permission_audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  user_email TEXT,
  user_roles TEXT[],
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  action TEXT NOT NULL,
  allowed BOOLEAN NOT NULL,
  reason TEXT,
  ip_address TEXT,
  user_agent TEXT,
  request_path TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建索引
CREATE INDEX idx_permission_audit_logs_user ON permission_audit_logs(user_id);
CREATE INDEX idx_permission_audit_logs_created ON permission_audit_logs(created_at DESC);
CREATE INDEX idx_permission_audit_logs_resource ON permission_audit_logs(resource_type, resource_id);
CREATE INDEX idx_permission_audit_logs_allowed ON permission_audit_logs(allowed);

-- 3. 创建审计日志视图
CREATE OR REPLACE VIEW permission_audit_summary AS
SELECT 
  user_email,
  resource_type,
  action,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN allowed THEN 1 ELSE 0 END) as allowed_count,
  SUM(CASE WHEN NOT allowed THEN 1 ELSE 0 END) as denied_count,
  MAX(created_at) as last_attempt
FROM permission_audit_logs
GROUP BY user_email, resource_type, action
ORDER BY last_attempt DESC;

-- 4. 创建清理旧日志的函数
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM permission_audit_logs
  WHERE created_at < NOW() - (days_to_keep || ' days')::INTERVAL;
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 5. 启用 RLS
ALTER TABLE permission_audit_logs ENABLE ROW LEVEL SECURITY;

-- 6. 创建 RLS 策略
-- 管理员可以查看所有审计日志
CREATE POLICY "admin_view_all_audit_logs" ON permission_audit_logs
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

-- 用户可以查看自己的审计日志
CREATE POLICY "users_view_own_audit_logs" ON permission_audit_logs
  FOR SELECT
  USING (user_id = auth.uid());

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '权限审计日志表创建完成！';
  RAISE NOTICE '已创建 permission_audit_logs 表和相关视图';
  RAISE NOTICE '==============================================';
END $$;

