-- =============================================
-- 医疗质控系统 - 质控规则初始化脚本
-- 版本: 2.0.0
-- 创建时间: 2024-12-25
-- 说明: 此脚本需要在用户档案创建后执行
-- =============================================

-- 注意：此脚本需要在有用户档案后执行
-- 如果没有用户档案，请先创建一个管理员用户档案

-- 临时创建一个系统管理员档案（如果不存在）
-- 请根据实际情况修改用户ID
DO $$
DECLARE
    admin_user_id UUID;
    admin_profile_id UUID;
BEGIN
    -- 检查是否已有管理员档案
    SELECT id INTO admin_profile_id FROM user_profiles WHERE role_type = 'admin' LIMIT 1;
    
    IF admin_profile_id IS NULL THEN
        -- 创建一个临时的系统管理员档案
        -- 注意：这里使用的是一个示例UUID，实际使用时需要替换为真实的auth.users ID
        INSERT INTO user_profiles (
            user_id, 
            username, 
            full_name, 
            email, 
            role_type,
            department_id,
            is_active
        ) VALUES (
            gen_random_uuid(), -- 临时UUID，实际应该是auth.users的真实ID
            'system_admin',
            '系统管理员',
            'admin@medqc.system',
            'admin',
            (SELECT id FROM departments WHERE code = 'INTERNAL' LIMIT 1),
            true
        ) RETURNING id INTO admin_profile_id;
        
        RAISE NOTICE '创建了临时系统管理员档案: %', admin_profile_id;
    END IF;
END $$;

-- 插入基础质控规则
INSERT INTO qc_rules (
    rule_code, 
    name, 
    description, 
    category, 
    rule_type, 
    severity, 
    target_sections, 
    check_logic,
    scoring_config,
    prompt_template,
    created_by
) VALUES
-- 完整性检查规则
(
    'R001', 
    '主诉完整性检查', 
    '检查病历中主诉部分是否完整记录，主诉应简明扼要地描述患者的主要症状', 
    'completeness', 
    'logical', 
    'major', 
    ARRAY['主诉'], 
    '{"type": "content_check", "required_sections": ["主诉"], "min_length": 5}',
    '{"default_deduction": 5, "max_deduction": 10, "weight_factor": 1.0}',
    '请检查以下病历的主诉部分是否完整：\n\n{content}\n\n评估标准：\n1. 主诉是否存在\n2. 主诉是否简明扼要\n3. 主诉是否描述了主要症状\n\n请给出评估结果和建议。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R002', 
    '现病史详细性检查', 
    '检查现病史记录是否详细完整，包括发病时间、症状发展过程、诊疗经过等', 
    'completeness', 
    'semantic', 
    'major', 
    ARRAY['现病史'], 
    '{"type": "content_analysis", "min_length": 100, "required_elements": ["发病时间", "症状发展", "诊疗经过"]}',
    '{"default_deduction": 8, "max_deduction": 15, "weight_factor": 1.2}',
    '请分析以下病历的现病史部分：\n\n{content}\n\n检查要点：\n1. 发病时间是否明确\n2. 症状发展过程是否详细\n3. 既往诊疗经过是否完整\n4. 内容是否逻辑清晰\n\n请评估并提供改进建议。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R003', 
    '诊断一致性检查', 
    '检查入院诊断与出院诊断的一致性，如有变更应有合理说明', 
    'consistency', 
    'semantic', 
    'critical', 
    ARRAY['入院诊断', '出院诊断'], 
    '{"type": "consistency_check", "compare_fields": ["入院诊断", "出院诊断"], "allow_refinement": true}',
    '{"default_deduction": 10, "max_deduction": 20, "weight_factor": 1.5}',
    '请比较以下病历的入院诊断和出院诊断：\n\n{content}\n\n分析要点：\n1. 诊断是否一致\n2. 如有变更，是否有合理依据\n3. 诊断是否符合临床表现\n4. 诊断编码是否正确\n\n请给出一致性评估结果。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R004', 
    '用药记录完整性', 
    '检查用药记录是否完整，包括药物名称、剂量、用法、疗程等', 
    'completeness', 
    'logical', 
    'minor', 
    ARRAY['用药记录', '医嘱'], 
    '{"type": "medication_check", "required_fields": ["药物名称", "剂量", "用法", "频次"]}',
    '{"default_deduction": 3, "max_deduction": 8, "weight_factor": 0.8}',
    '请检查以下病历的用药记录：\n\n{content}\n\n检查项目：\n1. 药物名称是否完整\n2. 剂量是否明确\n3. 用法用量是否规范\n4. 疗程是否合理\n\n请评估用药记录的完整性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R005', 
    '手术记录规范性', 
    '检查手术记录是否符合规范要求，包括手术指征、过程、结果等', 
    'compliance', 
    'semantic', 
    'critical', 
    ARRAY['手术记录'], 
    '{"type": "surgery_compliance", "required_sections": ["手术指征", "手术过程", "术中发现", "手术结果"]}',
    '{"default_deduction": 12, "max_deduction": 25, "weight_factor": 1.8}',
    '请评估以下手术记录的规范性：\n\n{content}\n\n评估要点：\n1. 手术指征是否明确\n2. 手术过程是否详细\n3. 术中发现是否完整\n4. 手术结果是否清楚\n5. 是否符合手术记录规范\n\n请给出规范性评估。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),

-- 准确性检查规则
(
    'R006', 
    '检验结果准确性', 
    '检查检验结果的记录是否准确，数值是否合理', 
    'accuracy', 
    'logical', 
    'major', 
    ARRAY['检验报告', '化验结果'], 
    '{"type": "lab_result_check", "check_ranges": true, "validate_units": true}',
    '{"default_deduction": 6, "max_deduction": 12, "weight_factor": 1.1}',
    '请检查以下检验结果的准确性：\n\n{content}\n\n检查要点：\n1. 数值是否在合理范围内\n2. 单位是否正确\n3. 结果是否与临床表现一致\n4. 异常结果是否有说明\n\n请评估检验结果的准确性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R007', 
    '时间逻辑一致性', 
    '检查病历中各时间点的逻辑一致性', 
    'consistency', 
    'logical', 
    'minor', 
    ARRAY['入院时间', '手术时间', '出院时间'], 
    '{"type": "time_logic_check", "validate_sequence": true}',
    '{"default_deduction": 4, "max_deduction": 8, "weight_factor": 0.9}',
    '请检查以下病历的时间逻辑：\n\n{content}\n\n检查要点：\n1. 入院时间是否合理\n2. 各项操作时间是否符合逻辑\n3. 出院时间是否合适\n4. 时间顺序是否正确\n\n请评估时间逻辑的一致性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),

-- 及时性检查规则
(
    'R008', 
    '病历书写及时性', 
    '检查病历书写是否及时，是否在规定时间内完成', 
    'timeliness', 
    'logical', 
    'major', 
    ARRAY['入院记录', '病程记录'], 
    '{"type": "timeliness_check", "max_delay_hours": 24}',
    '{"default_deduction": 7, "max_deduction": 15, "weight_factor": 1.3}',
    '请检查病历书写的及时性：\n\n{content}\n\n检查标准：\n1. 入院记录是否在24小时内完成\n2. 病程记录是否及时更新\n3. 重要检查结果是否及时记录\n4. 出院记录是否按时完成\n\n请评估书写及时性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),

-- 合规性检查规则
(
    'R009', 
    '知情同意书完整性', 
    '检查知情同意书是否完整，签字是否齐全', 
    'compliance', 
    'logical', 
    'critical', 
    ARRAY['知情同意书'], 
    '{"type": "consent_check", "required_signatures": ["患者", "医生"], "check_date": true}',
    '{"default_deduction": 15, "max_deduction": 30, "weight_factor": 2.0}',
    '请检查知情同意书的完整性：\n\n{content}\n\n检查要点：\n1. 同意书内容是否完整\n2. 患者签字是否齐全\n3. 医生签字是否规范\n4. 日期是否正确\n5. 是否符合法律要求\n\n请评估合规性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
),
(
    'R010', 
    '病历格式规范性', 
    '检查病历格式是否符合医院规范要求', 
    'compliance', 
    'logical', 
    'minor', 
    ARRAY['全部'], 
    '{"type": "format_check", "check_structure": true, "validate_headers": true}',
    '{"default_deduction": 2, "max_deduction": 5, "weight_factor": 0.5}',
    '请检查病历格式的规范性：\n\n{content}\n\n检查标准：\n1. 章节结构是否完整\n2. 标题格式是否规范\n3. 内容排版是否整齐\n4. 是否符合医院模板要求\n\n请评估格式规范性。',
    (SELECT id FROM user_profiles WHERE role_type = 'admin' LIMIT 1)
);

-- 显示插入的规则统计
SELECT 
    category,
    severity,
    COUNT(*) as rule_count
FROM qc_rules 
GROUP BY category, severity
ORDER BY category, severity;

-- 显示所有规则概览
SELECT 
    rule_code,
    name,
    category,
    severity,
    rule_type,
    is_active
FROM qc_rules 
ORDER BY rule_code;
