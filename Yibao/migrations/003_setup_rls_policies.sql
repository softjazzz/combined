-- 智慧医保临床实时质控系统 - RLS 策略配置
-- 文件: 003_setup_rls_policies.sql
-- 说明: 配置 Row Level Security 策略与角色权限

-- 1. 为所有表创建读取策略（authenticated 用户可读）
-- 规则分类表
CREATE POLICY "read_auth_yibao_rule_categories" ON yibao_rule_categories
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 规则主表
CREATE POLICY "read_auth_yibao_rules" ON yibao_rules
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 规则触发事件表
CREATE POLICY "read_auth_yibao_rule_triggers" ON yibao_rule_triggers
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 规则条件表
CREATE POLICY "read_auth_yibao_rule_conditions" ON yibao_rule_conditions
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 规则动作表
CREATE POLICY "read_auth_yibao_rule_actions" ON yibao_rule_actions
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 药品表
CREATE POLICY "read_auth_yibao_drugs" ON yibao_drugs
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 医疗服务表
CREATE POLICY "read_auth_yibao_medical_services" ON yibao_medical_services
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 违规记录表
CREATE POLICY "read_auth_yibao_violations" ON yibao_violations
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 审计任务表
CREATE POLICY "read_auth_yibao_audit_tasks" ON yibao_audit_tasks
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 审计结果表
CREATE POLICY "read_auth_yibao_audit_results" ON yibao_audit_results
    FOR SELECT USING (auth.role() IN ('authenticated', 'service_role'));

-- 2. 为所有表创建写入策略（仅 service_role 可写）
-- 规则分类表
CREATE POLICY "write_service_yibao_rule_categories" ON yibao_rule_categories
    FOR ALL USING (auth.role() = 'service_role');

-- 规则主表
CREATE POLICY "write_service_yibao_rules" ON yibao_rules
    FOR ALL USING (auth.role() = 'service_role');

-- 规则触发事件表
CREATE POLICY "write_service_yibao_rule_triggers" ON yibao_rule_triggers
    FOR ALL USING (auth.role() = 'service_role');

-- 规则条件表
CREATE POLICY "write_service_yibao_rule_conditions" ON yibao_rule_conditions
    FOR ALL USING (auth.role() = 'service_role');

-- 规则动作表
CREATE POLICY "write_service_yibao_rule_actions" ON yibao_rule_actions
    FOR ALL USING (auth.role() = 'service_role');

-- 药品表
CREATE POLICY "write_service_yibao_drugs" ON yibao_drugs
    FOR ALL USING (auth.role() = 'service_role');

-- 医疗服务表
CREATE POLICY "write_service_yibao_medical_services" ON yibao_medical_services
    FOR ALL USING (auth.role() = 'service_role');

-- 违规记录表
CREATE POLICY "write_service_yibao_violations" ON yibao_violations
    FOR ALL USING (auth.role() = 'service_role');

-- 审计任务表
CREATE POLICY "write_service_yibao_audit_tasks" ON yibao_audit_tasks
    FOR ALL USING (auth.role() = 'service_role');

-- 审计结果表
CREATE POLICY "write_service_yibao_audit_results" ON yibao_audit_results
    FOR ALL USING (auth.role() = 'service_role');

-- 3. 创建函数：检查用户是否有管理员权限（用于前端权限控制）
CREATE OR REPLACE FUNCTION is_admin_user()
RETURNS BOOLEAN AS $$
BEGIN
    -- 检查当前用户是否在 auth.users 表中且具有 admin 角色
    -- 这里可以根据实际的用户角色设计进行调整
    RETURN EXISTS (
        SELECT 1 FROM auth.users 
        WHERE id = auth.uid() 
        AND raw_user_meta_data->>'role' = 'admin'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. 创建函数：获取当前用户信息
CREATE OR REPLACE FUNCTION get_current_user_info()
RETURNS JSON AS $$
DECLARE
    user_info JSON;
BEGIN
    SELECT json_build_object(
        'id', id,
        'email', email,
        'role', COALESCE(raw_user_meta_data->>'role', 'user'),
        'department', COALESCE(raw_user_meta_data->>'department', ''),
        'display_name', COALESCE(raw_user_meta_data->>'display_name', email)
    ) INTO user_info
    FROM auth.users 
    WHERE id = auth.uid();
    
    RETURN COALESCE(user_info, '{"error": "User not found"}'::json);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 5. 授予必要的权限
-- 允许 authenticated 用户执行 SELECT 操作
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- 允许 service_role 执行所有操作
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- 6. 创建用于 Edge Functions 的辅助函数
CREATE OR REPLACE FUNCTION execute_rule_engine(
    context_data JSONB,
    event_type TEXT DEFAULT 'order.drug.submit'
)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    -- 这个函数将在 Edge Function 中实现具体逻辑
    -- 这里只是占位符，返回基本结构
    SELECT json_build_object(
        'success', true,
        'violations', '[]'::json,
        'message', 'Rule engine placeholder - implement in Edge Function'
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 7. 创建统计查询函数
CREATE OR REPLACE FUNCTION get_rule_statistics(
    start_date DATE DEFAULT CURRENT_DATE - INTERVAL '30 days',
    end_date DATE DEFAULT CURRENT_DATE
)
RETURNS JSON AS $$
DECLARE
    stats JSON;
BEGIN
    SELECT json_build_object(
        'total_violations', COUNT(*),
        'by_severity', json_object_agg(severity, cnt),
        'by_rule_type', json_object_agg(rule_type, rule_cnt),
        'date_range', json_build_object('start', start_date, 'end', end_date)
    ) INTO stats
    FROM (
        SELECT 
            v.severity,
            r.rule_type,
            COUNT(*) as cnt,
            COUNT(*) as rule_cnt
        FROM yibao_violations v
        JOIN yibao_rules r ON v.rule_id = r.id
        WHERE v.created_at::date BETWEEN start_date AND end_date
        GROUP BY v.severity, r.rule_type
    ) subq;
    
    RETURN COALESCE(stats, '{}'::json);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
