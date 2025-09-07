-- =============================================
-- RLS策略恢复计划
-- 建议在生产环境部署前执行
-- =============================================

-- 第一步：移除开发环境的开放策略
-- 这些策略允许匿名访问，仅适用于开发环境

DROP POLICY IF EXISTS "Allow anonymous access for development" ON medical_records;
DROP POLICY IF EXISTS "Allow anonymous access for development" ON qc_results;
DROP POLICY IF EXISTS "Allow anonymous access for development" ON qc_rules;
DROP POLICY IF EXISTS "Allow anonymous access for development" ON qc_analysis_cache;
DROP POLICY IF EXISTS "Allow anonymous access for development" ON qc_analysis_history;
DROP POLICY IF EXISTS "Allow anonymous access for development" ON user_roles;

-- 第二步：创建生产环境的安全策略

-- 1. 医疗记录访问策略
CREATE POLICY "医疗记录_管理员全权限" ON medical_records
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role IN ('admin', 'qc_manager')
    )
  );

CREATE POLICY "医疗记录_医生查看本人记录" ON medical_records
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'doctor'
      AND (
        department = ur.department OR
        patient_id = auth.uid()::text
      )
    )
  );

CREATE POLICY "医疗记录_质控人员查看权限" ON medical_records
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'qc_staff'
    )
  );

-- 2. 质控结果访问策略
CREATE POLICY "质控结果_管理员全权限" ON qc_results
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role IN ('admin', 'qc_manager')
    )
  );

CREATE POLICY "质控结果_质控人员查看编辑" ON qc_results
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'qc_staff'
    )
  );

CREATE POLICY "质控结果_医生查看本人相关" ON qc_results
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      JOIN medical_records mr ON mr.id = qc_results.record_id
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'doctor'
      AND mr.department = ur.department
    )
  );

-- 3. 质控规则访问策略
CREATE POLICY "质控规则_管理员全权限" ON qc_rules
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role IN ('admin', 'qc_manager')
    )
  );

CREATE POLICY "质控规则_其他用户只读" ON qc_rules
  FOR SELECT USING (
    is_active = true AND
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role IN ('qc_staff', 'doctor')
    )
  );

-- 4. 用户角色访问策略
CREATE POLICY "用户角色_管理员全权限" ON user_roles
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'admin'
    )
  );

CREATE POLICY "用户角色_用户查看自己" ON user_roles
  FOR SELECT USING (user_id = auth.uid());

-- 5. 分析结果访问策略（新增表）
CREATE POLICY "分析结果_管理员全权限" ON analytics_results
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role IN ('admin', 'qc_manager')
    )
  );

CREATE POLICY "分析结果_医生查看本科室" ON analytics_results
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'doctor'
      AND (
        dimension_values->>'doctor_id' = auth.uid()::text OR
        dimension_values->>'department' = ur.department
      )
    )
  );

-- 第三步：创建安全函数（可选）
-- 用于检查用户是否有特定权限

CREATE OR REPLACE FUNCTION check_user_permission(
  required_role TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_roles ur
    WHERE ur.user_id = auth.uid()
    AND ur.role = required_role
  );
END;
$$;

-- 第四步：创建审计日志（可选）
-- 记录敏感操作

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  action TEXT NOT NULL,
  table_name TEXT NOT NULL,
  record_id UUID,
  old_values JSONB,
  new_values JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 启用审计日志的RLS
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "审计日志_管理员查看" ON audit_logs
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = auth.uid()
      AND ur.role = 'admin'
    )
  );

-- =============================================
-- 使用说明
-- =============================================

-- 1. 开发阶段：保持当前开放策略，便于开发测试
-- 2. 测试阶段：在测试环境先执行此脚本验证
-- 3. 生产部署：正式环境必须执行此脚本
-- 4. 监控：定期检查RLS策略是否按预期工作

-- 验证命令：
-- SELECT * FROM medical_records; -- 应该根据用户角色返回不同结果
-- SELECT * FROM qc_results; -- 应该根据用户角色返回不同结果 