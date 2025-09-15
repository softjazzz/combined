-- 规则版本管理表
-- 用于支持规则快照、回滚和版本对比功能

-- 规则版本快照表
CREATE TABLE IF NOT EXISTS yibao_rule_versions (
    id BIGSERIAL PRIMARY KEY,
    version_name VARCHAR(100) NOT NULL, -- 版本名称，如 "v1.0.0", "hotfix-20241210"
    description TEXT, -- 版本描述
    created_by UUID REFERENCES auth.users(id), -- 创建者
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE, -- 是否为当前活跃版本
    
    -- 快照数据（JSON格式存储完整规则集）
    rules_snapshot JSONB NOT NULL, -- 规则快照
    conditions_snapshot JSONB NOT NULL, -- 条件快照  
    actions_snapshot JSONB NOT NULL, -- 动作快照
    triggers_snapshot JSONB NOT NULL, -- 触发器快照
    
    -- 版本统计信息
    total_rules INTEGER DEFAULT 0,
    active_rules INTEGER DEFAULT 0,
    
    -- 性能基准数据
    benchmark_data JSONB, -- 版本性能基准测试结果
    
    UNIQUE(version_name)
);

-- 规则变更历史表
CREATE TABLE IF NOT EXISTS yibao_rule_changes (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES yibao_rules(id),
    version_id BIGINT REFERENCES yibao_rule_versions(id),
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('create', 'update', 'delete', 'enable', 'disable')),
    old_data JSONB, -- 变更前数据
    new_data JSONB, -- 变更后数据
    changed_by UUID REFERENCES auth.users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_reason TEXT -- 变更原因
);

-- 版本部署历史表
CREATE TABLE IF NOT EXISTS yibao_version_deployments (
    id BIGSERIAL PRIMARY KEY,
    version_id BIGINT REFERENCES yibao_rule_versions(id),
    deployed_by UUID REFERENCES auth.users(id),
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    rollback_from_version_id BIGINT REFERENCES yibao_rule_versions(id), -- 如果是回滚，记录原版本
    deployment_status VARCHAR(20) DEFAULT 'pending' CHECK (deployment_status IN ('pending', 'success', 'failed', 'rolled_back')),
    deployment_notes TEXT,
    
    -- 部署性能指标
    deployment_duration_ms INTEGER, -- 部署耗时
    affected_rules_count INTEGER, -- 影响的规则数量
    validation_results JSONB -- 部署前验证结果
);

-- 创建索引
CREATE INDEX idx_rule_versions_active ON yibao_rule_versions(is_active) WHERE is_active = true;
CREATE INDEX idx_rule_versions_created_at ON yibao_rule_versions(created_at DESC);
CREATE INDEX idx_rule_changes_rule_id ON yibao_rule_changes(rule_id);
CREATE INDEX idx_rule_changes_version_id ON yibao_rule_changes(version_id);
CREATE INDEX idx_rule_changes_changed_at ON yibao_rule_changes(changed_at DESC);
CREATE INDEX idx_version_deployments_version_id ON yibao_version_deployments(version_id);
CREATE INDEX idx_version_deployments_deployed_at ON yibao_version_deployments(deployed_at DESC);

-- RLS 策略
ALTER TABLE yibao_rule_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_version_deployments ENABLE ROW LEVEL SECURITY;

-- 允许认证用户读取版本信息
CREATE POLICY "Allow authenticated users to read rule versions" ON yibao_rule_versions
    FOR SELECT TO authenticated USING (true);

-- 允许管理员用户管理版本
CREATE POLICY "Allow admin users to manage rule versions" ON yibao_rule_versions
    FOR ALL TO authenticated 
    USING (auth.jwt() ->> 'role' = 'admin');

-- 允许认证用户读取变更历史
CREATE POLICY "Allow authenticated users to read rule changes" ON yibao_rule_changes
    FOR SELECT TO authenticated USING (true);

-- 允许管理员用户管理变更历史
CREATE POLICY "Allow admin users to manage rule changes" ON yibao_rule_changes
    FOR ALL TO authenticated 
    USING (auth.jwt() ->> 'role' = 'admin');

-- 允许认证用户读取部署历史
CREATE POLICY "Allow authenticated users to read version deployments" ON yibao_version_deployments
    FOR SELECT TO authenticated USING (true);

-- 允许管理员用户管理部署历史
CREATE POLICY "Allow admin users to manage version deployments" ON yibao_version_deployments
    FOR ALL TO authenticated 
    USING (auth.jwt() ->> 'role' = 'admin');

-- 创建函数：获取当前活跃版本
CREATE OR REPLACE FUNCTION get_active_rule_version()
RETURNS yibao_rule_versions AS $$
DECLARE
    active_version yibao_rule_versions;
BEGIN
    SELECT * INTO active_version 
    FROM yibao_rule_versions 
    WHERE is_active = true 
    ORDER BY created_at DESC 
    LIMIT 1;
    
    RETURN active_version;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建函数：创建规则快照
CREATE OR REPLACE FUNCTION create_rule_snapshot(
    p_version_name VARCHAR(100),
    p_description TEXT DEFAULT NULL,
    p_created_by UUID DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    v_version_id BIGINT;
    v_rules_data JSONB;
    v_conditions_data JSONB;
    v_actions_data JSONB;
    v_triggers_data JSONB;
    v_total_rules INTEGER;
    v_active_rules INTEGER;
BEGIN
    -- 获取当前规则数据
    SELECT jsonb_agg(to_jsonb(r.*)) INTO v_rules_data
    FROM yibao_rules r;
    
    SELECT jsonb_agg(to_jsonb(c.*)) INTO v_conditions_data
    FROM yibao_rule_conditions c;
    
    SELECT jsonb_agg(to_jsonb(a.*)) INTO v_actions_data
    FROM yibao_rule_actions a;
    
    SELECT jsonb_agg(to_jsonb(t.*)) INTO v_triggers_data
    FROM yibao_rule_triggers t;
    
    -- 统计信息
    SELECT COUNT(*), COUNT(*) FILTER (WHERE enabled = true)
    INTO v_total_rules, v_active_rules
    FROM yibao_rules;
    
    -- 创建版本记录
    INSERT INTO yibao_rule_versions (
        version_name, description, created_by,
        rules_snapshot, conditions_snapshot, actions_snapshot, triggers_snapshot,
        total_rules, active_rules
    ) VALUES (
        p_version_name, p_description, p_created_by,
        v_rules_data, v_conditions_data, v_actions_data, v_triggers_data,
        v_total_rules, v_active_rules
    ) RETURNING id INTO v_version_id;
    
    RETURN v_version_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
