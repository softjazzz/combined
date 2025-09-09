-- 智慧医保临床实时质控系统 - 数据库迁移 V1.1
-- 文件: 001_reset_and_create_unified_rules.sql
-- 说明: 创建统一规则域 + 业务/审计表结构

-- 1. 创建枚举类型
CREATE TYPE rule_severity AS ENUM ('info', 'warn', 'block');

-- 2. 创建规则分类表
CREATE TABLE yibao_rule_categories (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 创建规则主表
CREATE TABLE yibao_rules (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id BIGINT REFERENCES yibao_rule_categories(id),
    rule_type TEXT NOT NULL,
    severity rule_severity DEFAULT 'warn',
    enabled BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 创建规则触发事件表
CREATE TABLE yibao_rule_triggers (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL
);

-- 5. 创建规则条件表
CREATE TABLE yibao_rule_conditions (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,
    expression_json JSONB NOT NULL
);

-- 6. 创建规则动作表
CREATE TABLE yibao_rule_actions (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    message_template TEXT
);

-- 7. 创建药品主数据表
CREATE TABLE yibao_drugs (
    drug_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    atc_code TEXT,
    specs JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- 8. 创建医疗服务项目表
CREATE TABLE yibao_medical_services (
    service_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    metadata JSONB DEFAULT '{}'
);

-- 9. 创建违规记录表
CREATE TABLE yibao_violations (
    id BIGSERIAL PRIMARY KEY,
    visit_id TEXT NOT NULL,
    rule_id BIGINT REFERENCES yibao_rules(id),
    severity rule_severity NOT NULL,
    snapshot JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. 创建审计任务表
CREATE TABLE yibao_audit_tasks (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES yibao_rules(id),
    status TEXT DEFAULT 'pending',
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. 创建审计结果表
CREATE TABLE yibao_audit_results (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES yibao_audit_tasks(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    detail JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. 创建索引
CREATE INDEX idx_yibao_rules_type_enabled ON yibao_rules(rule_type, enabled);
CREATE INDEX idx_yibao_rule_triggers_event ON yibao_rule_triggers(event_type);
CREATE INDEX idx_yibao_rule_conditions_gin ON yibao_rule_conditions USING GIN(expression_json jsonb_path_ops);
CREATE INDEX idx_yibao_violations_visit_id ON yibao_violations(visit_id);
CREATE INDEX idx_yibao_violations_created_at ON yibao_violations(created_at);

-- 13. 创建触发器函数（自动更新 updated_at）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 14. 为需要的表添加触发器
CREATE TRIGGER trg_yibao_rule_categories_updated_at
    BEFORE UPDATE ON yibao_rule_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_yibao_rules_updated_at
    BEFORE UPDATE ON yibao_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 15. 创建统计视图
CREATE VIEW yibao_rule_statistics AS
SELECT 
    r.rule_type,
    COUNT(v.id) as hits,
    COUNT(DISTINCT v.visit_id) as unique_visits
FROM yibao_rules r
LEFT JOIN yibao_violations v ON r.id = v.rule_id
GROUP BY r.rule_type;

-- 16. 启用 RLS (Row Level Security)
ALTER TABLE yibao_rule_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_drugs ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_medical_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_audit_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_audit_results ENABLE ROW LEVEL SECURITY;