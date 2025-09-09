-- 智慧医保临床实时质控系统 - 种子数据
-- 文件: 002_seed_minimal_rules.sql
-- 说明: 初始化基础规则分类和示例规则

-- 1. 插入规则分类
INSERT INTO yibao_rule_categories (code, name) VALUES
('batch_1', '第一批：性别年龄限制'),
('batch_2', '第二批：手术折价规则'),
('batch_3', '第三批：保险类型限制'),
('batch_4', '第四批：就诊方式限制'),
('batch_5', '第五批：机构级别限制'),
('batch_6', '第六批：疗程计算规则');

-- 2. 插入示例规则
INSERT INTO yibao_rules (code, name, category_id, rule_type, severity, enabled, metadata) VALUES
-- 年龄限制示例
('DRUG_AGE_DEMO', '药品年龄限制示例', 
 (SELECT id FROM yibao_rule_categories WHERE code = 'batch_1'), 
 'drug_age', 'warn', true, 
 '{"description": "某药品限14周岁及以下儿童使用", "source": "医保目录"}'),

-- 性别限制示例  
('DRUG_GENDER_DEMO', '药品性别限制示例',
 (SELECT id FROM yibao_rule_categories WHERE code = 'batch_1'),
 'drug_gender', 'warn', true,
 '{"description": "某药品限女性患者使用", "source": "医保目录"}'),

-- 就诊方式限制示例
('DRUG_VISIT_DEMO', '药品就诊方式限制示例',
 (SELECT id FROM yibao_rule_categories WHERE code = 'batch_4'),
 'visit_type', 'block', true,
 '{"description": "某药品限住院患者使用", "source": "医保目录"}');

-- 3. 插入触发事件
INSERT INTO yibao_rule_triggers (rule_id, event_type) VALUES
((SELECT id FROM yibao_rules WHERE code = 'DRUG_AGE_DEMO'), 'order.drug.submit'),
((SELECT id FROM yibao_rules WHERE code = 'DRUG_GENDER_DEMO'), 'order.drug.submit'),
((SELECT id FROM yibao_rules WHERE code = 'DRUG_VISIT_DEMO'), 'order.drug.submit');

-- 4. 插入规则条件（JSON表达式）
INSERT INTO yibao_rule_conditions (rule_id, priority, expression_json) VALUES
-- 年龄限制条件：患者年龄 > 14 且 药品代码匹配
((SELECT id FROM yibao_rules WHERE code = 'DRUG_AGE_DEMO'), 1, '{
  "all": [
    {"fact": "patient.age", "op": ">", "value": 14},
    {"fact": "order.drug_code", "op": "in", "value": ["DEMO_DRUG_001", "DEMO_DRUG_002"]}
  ]
}'),

-- 性别限制条件：患者性别为男性 且 药品代码匹配
((SELECT id FROM yibao_rules WHERE code = 'DRUG_GENDER_DEMO'), 1, '{
  "all": [
    {"fact": "patient.gender", "op": "==", "value": "M"},
    {"fact": "order.drug_code", "op": "==", "value": "DEMO_DRUG_FEMALE"}
  ]
}'),

-- 就诊方式限制条件：门诊患者 且 药品代码匹配
((SELECT id FROM yibao_rules WHERE code = 'DRUG_VISIT_DEMO'), 1, '{
  "all": [
    {"fact": "visit.type", "op": "==", "value": "OUTPATIENT"},
    {"fact": "order.drug_code", "op": "==", "value": "DEMO_DRUG_INPATIENT"}
  ]
}');

-- 5. 插入规则动作
INSERT INTO yibao_rule_actions (rule_id, action_type, message_template) VALUES
((SELECT id FROM yibao_rules WHERE code = 'DRUG_AGE_DEMO'), 'warn', 
 '【提醒】{order.drug_name} 限14周岁及以下儿童使用，当前患者{patient.age}岁，医保可能不予支付。请确认是否继续？'),

((SELECT id FROM yibao_rules WHERE code = 'DRUG_GENDER_DEMO'), 'warn',
 '【提醒】{order.drug_name} 限女性患者使用，当前患者为男性，医保可能不予支付。请确认是否继续？'),

((SELECT id FROM yibao_rules WHERE code = 'DRUG_VISIT_DEMO'), 'intercept',
 '【拦截】{order.drug_name} 限住院患者使用，门诊患者不可开具此药品。请选择其他药品。');

-- 6. 插入示例药品数据
INSERT INTO yibao_drugs (drug_code, name, atc_code, specs, metadata) VALUES
('DEMO_DRUG_001', '示例儿童药品A', 'A01AA01', '{"spec": "10mg/片", "package": "28片/盒"}', 
 '{"age_limit": "≤14岁", "indication": "儿童感冒"}'),
('DEMO_DRUG_002', '示例儿童药品B', 'A01AA02', '{"spec": "5ml/支", "package": "10支/盒"}', 
 '{"age_limit": "≤14岁", "indication": "儿童咳嗽"}'),
('DEMO_DRUG_FEMALE', '示例女性专用药', 'G03AA01', '{"spec": "2mg/片", "package": "21片/盒"}', 
 '{"gender_limit": "女性", "indication": "妇科疾病"}'),
('DEMO_DRUG_INPATIENT', '示例住院专用药', 'J01AA01', '{"spec": "500mg/瓶", "package": "1瓶"}', 
 '{"visit_limit": "住院", "indication": "严重感染"}');

-- 7. 插入示例医疗服务项目
INSERT INTO yibao_medical_services (service_code, name, category, metadata) VALUES
('DEMO_SURGERY_001', '示例手术项目A', '外科手术', '{"price_rule": "按规定折价", "level": "三级"}'),
('DEMO_EXAM_001', '示例检查项目A', '影像检查', '{"price_rule": "全额收费", "equipment": "CT"}'),
('DEMO_LAB_001', '示例化验项目A', '实验室检查', '{"price_rule": "全额收费", "method": "生化"}');

-- 8. 插入示例违规记录（用于测试统计功能）
INSERT INTO yibao_violations (visit_id, rule_id, severity, snapshot) VALUES
('V20240101001', (SELECT id FROM yibao_rules WHERE code = 'DRUG_AGE_DEMO'), 'warn', 
 '{"patient": {"age": 18, "gender": "M"}, "order": {"drug_code": "DEMO_DRUG_001", "drug_name": "示例儿童药品A"}, "visit": {"type": "OUTPATIENT"}}'),
('V20240101002', (SELECT id FROM yibao_rules WHERE code = 'DRUG_GENDER_DEMO'), 'warn',
 '{"patient": {"age": 25, "gender": "M"}, "order": {"drug_code": "DEMO_DRUG_FEMALE", "drug_name": "示例女性专用药"}, "visit": {"type": "OUTPATIENT"}}'),
('V20240101003', (SELECT id FROM yibao_rules WHERE code = 'DRUG_VISIT_DEMO'), 'block',
 '{"patient": {"age": 30, "gender": "F"}, "order": {"drug_code": "DEMO_DRUG_INPATIENT", "drug_name": "示例住院专用药"}, "visit": {"type": "OUTPATIENT"}}');