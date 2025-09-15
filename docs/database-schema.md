# 数据库设计文档（Supabase / PostgreSQL）

> 描述医保规则相关表结构、字段与约束，并给出索引与关系建议。

## 目录
- 表结构概览
- 字段说明与约束
- 关系与索引
- 示例建表 SQL
- 数据示例
- 维护与最佳实践

## 表结构概览
- yibao_rules（规则主表）
- yibao_rule_triggers（触发事件）
- yibao_rule_conditions（条件配置）
- yibao_rule_actions（动作配置）

## 字段说明与约束

### yibao_rules
- id: bigint PK
- code: varchar UNIQUE NOT NULL（如 DRUG_INSURANCE_TYPE_001）
- name: varchar NOT NULL（如 “疤痕止痒软化膏 - 保险类型限制”）
- rule_type: varchar NOT NULL（参考规则类型映射）
- severity: varchar NOT NULL（info|warn|block）
- enabled: boolean NOT NULL DEFAULT true
- version: int NOT NULL DEFAULT 1
- category_id: varchar NULL（batch_1~batch_5 等）
- description: text NULL
- metadata: jsonb NOT NULL DEFAULT '{}'::jsonb
- created_at: timestamptz NOT NULL DEFAULT now()
- updated_at: timestamptz NOT NULL DEFAULT now()

业务约束：
- code 全局唯一；
- name 建议唯一性+版本化（结合 version）；
- rule_type/severity 采用枚举型受控值；

### yibao_rule_triggers
- id: bigint PK
- rule_id: bigint FK -> yibao_rules.id
- event_type: varchar NOT NULL（如 encounter_created、order_created 等）
- priority: int NOT NULL DEFAULT 100

### yibao_rule_conditions
- id: bigint PK
- rule_id: bigint FK -> yibao_rules.id
- priority: int NOT NULL DEFAULT 100
- expression_json: jsonb NOT NULL（条件表达式，AND/OR 嵌套，字段/运算符/值）

### yibao_rule_actions
- id: bigint PK
- rule_id: bigint FK -> yibao_rules.id
- action_type: varchar NOT NULL（intercept|warn|notify）
- message_template: text NOT NULL

## 关系与索引
- 关系：
  - yibao_rules 1 - N yibao_rule_triggers
  - yibao_rules 1 - N yibao_rule_conditions
  - yibao_rules 1 - N yibao_rule_actions
- 索引建议：
  - yibao_rules(code) UNIQUE
  - yibao_rules(rule_type)
  - yibao_rules(severity)
  - yibao_rules(enabled)
  - yibao_rules(updated_at DESC)
  - yibao_rules(name gist_trgm_ops) 以支持模糊搜索（需 pg_trgm）
  - 子表外键列 rule_id 索引

## 示例建表 SQL（参考）
```sql
-- 需启用扩展：CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS yibao_rules (
  id           BIGSERIAL PRIMARY KEY,
  code         VARCHAR(128) NOT NULL UNIQUE,
  name         VARCHAR(512) NOT NULL,
  rule_type    VARCHAR(64) NOT NULL,
  severity     VARCHAR(16) NOT NULL CHECK (severity IN ('info','warn','block')),
  enabled      BOOLEAN NOT NULL DEFAULT TRUE,
  version      INT NOT NULL DEFAULT 1,
  category_id  VARCHAR(64),
  description  TEXT,
  metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rules_rule_type ON yibao_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_rules_severity ON yibao_rules(severity);
CREATE INDEX IF NOT EXISTS idx_rules_enabled ON yibao_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_rules_updated_at ON yibao_rules(updated_at DESC);
-- 可选：模糊搜索
-- CREATE INDEX IF NOT EXISTS idx_rules_name_trgm ON yibao_rules USING gist (name gist_trgm_ops);

CREATE TABLE IF NOT EXISTS yibao_rule_triggers (
  id          BIGSERIAL PRIMARY KEY,
  rule_id     BIGINT NOT NULL REFERENCES yibao_rules(id) ON DELETE CASCADE,
  event_type  VARCHAR(64) NOT NULL,
  priority    INT NOT NULL DEFAULT 100
);
CREATE INDEX IF NOT EXISTS idx_rule_triggers_rule_id ON yibao_rule_triggers(rule_id);

CREATE TABLE IF NOT EXISTS yibao_rule_conditions (
  id               BIGSERIAL PRIMARY KEY,
  rule_id          BIGINT NOT NULL REFERENCES yibao_rules(id) ON DELETE CASCADE,
  priority         INT NOT NULL DEFAULT 100,
  expression_json  JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rule_conditions_rule_id ON yibao_rule_conditions(rule_id);

CREATE TABLE IF NOT EXISTS yibao_rule_actions (
  id                BIGSERIAL PRIMARY KEY,
  rule_id           BIGINT NOT NULL REFERENCES yibao_rules(id) ON DELETE CASCADE,
  action_type       VARCHAR(32) NOT NULL CHECK (action_type IN ('intercept','warn','notify')),
  message_template  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rule_actions_rule_id ON yibao_rule_actions(rule_id);
```

## 数据示例
```json
{
  "rules": [
    {
      "id": 1,
      "code": "DRUG_INSURANCE_TYPE_001",
      "name": "疤痕止痒软化膏 - 保险类型限制",
      "rule_type": "drug_insurance_type",
      "severity": "warn",
      "enabled": true,
      "version": 1,
      "category_id": "batch_3",
      "description": "对某药品按保险类型进行限制",
      "metadata": {"owner":"admin","tags":["药品","医保"]},
      "updated_at": "2025-09-08T10:00:00Z"
    }
  ],
  "conditions": [
    {"rule_id":1,"priority":100,"expression_json":{"op":"AND","conditions":[{"field":"patient.insurance_type","op":"IN","value":["城镇职工","城乡居民"]}]}}
  ],
  "actions": [
    {"rule_id":1,"action_type":"intercept","message_template":"当前患者保险类型不允许开立该药品"}
  ],
  "triggers": [
    {"rule_id":1,"event_type":"order_created","priority":100}
  ]
}
```

## 维护与最佳实践
- 字典/映射：在前端维护 rule_type -> 文案/颜色 的映射；后端统一返回英文标识，减少多语冗余。
- 版本管理：变更逻辑时递增 version，并保留历史（可独立建 yibao_rule_versions）。
- 软删除：优先使用 enabled=false 与描述标注原因；确需物理删除时注意级联。
- 审计：对关键表启用行级审计（触发器或外部审计表），记录谁在何时修改了什么。

