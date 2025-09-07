-- Minimal seed data for categories and sample rules
begin;

-- 1) Categories (batches)
INSERT INTO yibao_rule_categories(code, name)
VALUES
  ('batch_1', '第一批 基础限制'),
  ('batch_2', '第二批 手术折价'),
  ('batch_4', '第四批 药品限就医方式')
ON CONFLICT (code) DO NOTHING;

-- helper to get category ids
WITH c AS (
  SELECT id, code FROM yibao_rule_categories
)
-- 2) Sample rule: 药品限儿童使用（示例：某些药品限≤14岁）
INSERT INTO yibao_rules(code, name, category_id, rule_type, severity, enabled, metadata)
SELECT 'DRUG_AGE_DEMO', '药品限儿童使用（示例）', c.id, 'drug_age', 'block', true, jsonb_build_object('source','seed_demo')
FROM c WHERE c.code='batch_1'
ON CONFLICT (code) DO NOTHING;

-- Attach trigger
INSERT INTO yibao_rule_triggers(rule_id, event_type)
SELECT r.id, 'order.drug.submit' FROM yibao_rules r WHERE r.code='DRUG_AGE_DEMO'
ON CONFLICT DO NOTHING;

-- Conditions: age > 14 AND drug_code IN (...)
INSERT INTO yibao_rule_conditions(rule_id, priority, expression_json)
SELECT r.id, 1,
       jsonb_build_object('all', jsonb_build_array(
         jsonb_build_object('fact','patient.age','op','>','value',14),
         jsonb_build_object('fact','order.drug_code','op','in','value', jsonb_build_array('DEMO001','DEMO002'))
       ))
FROM yibao_rules r WHERE r.code='DRUG_AGE_DEMO';

-- Action: intercept with message
INSERT INTO yibao_rule_actions(rule_id, action_type, message_template)
SELECT r.id, 'intercept', '【拦截】该药品限儿童使用，当前年龄={patient.age}。药品代码={order.drug_code}'
FROM yibao_rules r WHERE r.code='DRUG_AGE_DEMO';

-- 3) Sample rule: 药品区分性别（示例：某药限男性）
INSERT INTO yibao_rules(code, name, category_id, rule_type, severity, enabled, metadata)
SELECT 'DRUG_GENDER_DEMO', '药品限男性（示例）', c.id, 'drug_gender', 'warn', true, jsonb_build_object('source','seed_demo')
FROM yibao_rule_categories c WHERE c.code='batch_1'
ON CONFLICT (code) DO NOTHING;

INSERT INTO yibao_rule_triggers(rule_id, event_type)
SELECT r.id, 'order.drug.submit' FROM yibao_rules r WHERE r.code='DRUG_GENDER_DEMO'
ON CONFLICT DO NOTHING;

INSERT INTO yibao_rule_conditions(rule_id, priority, expression_json)
SELECT r.id, 1,
       jsonb_build_object('all', jsonb_build_array(
         jsonb_build_object('fact','patient.gender','op','==','value','F'),
         jsonb_build_object('fact','order.drug_code','op','in','value', jsonb_build_array('DEMO101'))
       ))
FROM yibao_rules r WHERE r.code='DRUG_GENDER_DEMO';

INSERT INTO yibao_rule_actions(rule_id, action_type, message_template)
SELECT r.id, 'warn', '【警告】该药品限男性使用，当前性别={patient.gender}。药品代码={order.drug_code}'
FROM yibao_rules r WHERE r.code='DRUG_GENDER_DEMO';

-- 4) Sample rule: 药品限就医方式（住院）
INSERT INTO yibao_rules(code, name, category_id, rule_type, severity, enabled, metadata)
SELECT 'DRUG_VISIT_DEMO', '药品限住院使用（示例）', c.id, 'visit_type', 'block', true, jsonb_build_object('source','seed_demo')
FROM yibao_rule_categories c WHERE c.code='batch_4'
ON CONFLICT (code) DO NOTHING;

INSERT INTO yibao_rule_triggers(rule_id, event_type)
SELECT r.id, 'order.drug.submit' FROM yibao_rules r WHERE r.code='DRUG_VISIT_DEMO'
ON CONFLICT DO NOTHING;

INSERT INTO yibao_rule_conditions(rule_id, priority, expression_json)
SELECT r.id, 1,
       jsonb_build_object('all', jsonb_build_array(
         jsonb_build_object('fact','visit.type','op','!=','value','INPATIENT'),
         jsonb_build_object('fact','order.drug_code','op','in','value', jsonb_build_array('DEMO201'))
       ))
FROM yibao_rules r WHERE r.code='DRUG_VISIT_DEMO';

INSERT INTO yibao_rule_actions(rule_id, action_type, message_template)
SELECT r.id, 'intercept', '【拦截】该药品限住院使用，当前就诊类型={visit.type}。药品代码={order.drug_code}'
FROM yibao_rules r WHERE r.code='DRUG_VISIT_DEMO';

commit;
