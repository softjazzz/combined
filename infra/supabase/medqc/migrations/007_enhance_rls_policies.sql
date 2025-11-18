-- ============================================================================
-- 增强 RLS 策略
-- 版本: 007
-- 描述: 实现基于角色的细粒度行级安全策略
-- 日期: 2025-10-12
-- ============================================================================

-- 0. 确保 user_roles 表存在（如果不存在则创建）
CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'qc_manager', 'qc_staff', 'doctor')),
  hospital_id TEXT,
  department TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, role)
);

-- 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- 启用 RLS（如果还没启用）
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- 1. 删除旧的简单策略（如果存在）
DROP POLICY IF EXISTS "认证用户可以查看医疗记录" ON medical_records;
DROP POLICY IF EXISTS "认证用户可以查看质控规则" ON qc_rules;
DROP POLICY IF EXISTS "认证用户可以查看质控结果" ON qc_results;

-- 2. 创建辅助函数

-- 获取用户角色
CREATE OR REPLACE FUNCTION get_user_roles(p_user_id UUID)
RETURNS TEXT[] AS $$
  SELECT ARRAY_AGG(role) 
  FROM user_roles 
  WHERE user_id = p_user_id;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 检查用户是否有指定角色
CREATE OR REPLACE FUNCTION has_role(p_user_id UUID, p_role TEXT)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = p_user_id AND role = p_role
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 检查用户是否有任意一个角色
CREATE OR REPLACE FUNCTION has_any_role(p_user_id UUID, p_roles TEXT[])
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = p_user_id AND role = ANY(p_roles)
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 3. Medical Records 策略

-- 管理员和质控人员可以查看所有记录
CREATE POLICY "admin_qc_view_all_medical_records" ON medical_records
  FOR SELECT
  USING (
    has_any_role(
      auth.uid(), 
      ARRAY['admin', 'qc_manager', 'qc_staff']
    )
  );

-- 医生只能查看自己创建的记录
CREATE POLICY "doctor_view_own_medical_records" ON medical_records
  FOR SELECT
  USING (
    has_role(auth.uid(), 'doctor') AND
    created_by = auth.uid()
  );

-- 管理员和质控管理员可以创建记录
CREATE POLICY "admin_qc_manager_create_medical_records" ON medical_records
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 管理员和质控管理员可以更新记录
CREATE POLICY "admin_qc_manager_update_medical_records" ON medical_records
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 只有管理员可以删除记录
CREATE POLICY "admin_delete_medical_records" ON medical_records
  FOR DELETE
  USING (has_role(auth.uid(), 'admin'));

-- 4. QC Rules 策略

-- 所有认证用户可以查看规则
CREATE POLICY "authenticated_view_qc_rules" ON qc_rules
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 管理员和质控管理员可以创建规则
CREATE POLICY "admin_qc_manager_create_qc_rules" ON qc_rules
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 管理员和质控管理员可以更新规则
CREATE POLICY "admin_qc_manager_update_qc_rules" ON qc_rules
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 只有管理员可以删除规则
CREATE POLICY "admin_delete_qc_rules" ON qc_rules
  FOR DELETE
  USING (has_role(auth.uid(), 'admin'));

-- 5. QC Results 策略

-- 所有认证用户可以查看质控结果
CREATE POLICY "authenticated_view_qc_results" ON qc_results
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 质控人员可以创建结果
CREATE POLICY "qc_staff_create_qc_results" ON qc_results
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager', 'qc_staff'])
  );

-- 质控人员可以更新结果
CREATE POLICY "qc_staff_update_qc_results" ON qc_results
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager', 'qc_staff'])
  );

-- 管理员和质控管理员可以删除结果
CREATE POLICY "admin_qc_manager_delete_qc_results" ON qc_results
  FOR DELETE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 6. User Roles 策略

-- 用户可以查看自己的角色
CREATE POLICY "users_view_own_roles" ON user_roles
  FOR SELECT
  USING (user_id = auth.uid());

-- 管理员可以查看所有角色
CREATE POLICY "admin_view_all_roles" ON user_roles
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

-- 只有管理员可以管理角色
CREATE POLICY "admin_manage_roles" ON user_roles
  FOR ALL
  USING (has_role(auth.uid(), 'admin'));

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE 'RLS 策略增强完成！';
  RAISE NOTICE '已创建基于角色的细粒度访问控制策略';
  RAISE NOTICE '==============================================';
END $$;

