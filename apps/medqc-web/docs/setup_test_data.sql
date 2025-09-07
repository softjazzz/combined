-- =====================================================
-- 医疗质控系统 - 测试数据初始化脚本
-- =====================================================
-- 用途: 在 Supabase SQL Editor 中运行，创建测试数据
-- 版本: v1.0
-- 日期: 2025-08-29
-- =====================================================

-- 1. 创建测试部门
-- =====================================================
INSERT INTO departments (id, name, code, description, category, is_active, sort_order) 
VALUES 
  (
    '11111111-1111-1111-1111-111111111111',
    '测试部门',
    'TEST_DEPT',
    '用于API测试的部门',
    'clinical',
    true,
    1
  ),
  (
    '33333333-3333-3333-3333-333333333333',
    '内科',
    'INTERNAL',
    '内科医学部',
    'clinical',
    true,
    2
  ),
  (
    '44444444-4444-4444-4444-444444444444',
    '外科',
    'SURGERY',
    '外科医学部',
    'clinical',
    true,
    3
  ),
  (
    '55555555-5555-5555-5555-555555555555',
    '急诊科',
    'EMERGENCY',
    '急诊医学科',
    'clinical',
    true,
    4
  )
ON CONFLICT (id) DO NOTHING;

-- 2. 创建测试用户
-- =====================================================
INSERT INTO user_profiles (
  id, 
  username, 
  full_name, 
  email, 
  phone,
  department_id, 
  role_type, 
  job_title,
  is_active
) 
VALUES 
  (
    '22222222-2222-2222-2222-222222222222',
    'testuser',
    '测试用户',
    'test@example.com',
    '13800138000',
    '11111111-1111-1111-1111-111111111111',
    'doctor',
    '主治医师',
    true
  ),
  (
    '66666666-6666-6666-6666-666666666666',
    'doctor_zhang',
    '张医生',
    'zhang@hospital.com',
    '13800138001',
    '33333333-3333-3333-3333-333333333333',
    'doctor',
    '副主任医师',
    true
  ),
  (
    '77777777-7777-7777-7777-777777777777',
    'doctor_li',
    '李医生',
    'li@hospital.com',
    '13800138002',
    '44444444-4444-4444-4444-444444444444',
    'doctor',
    '主任医师',
    true
  ),
  (
    '88888888-8888-8888-8888-888888888888',
    'nurse_wang',
    '王护士',
    'wang@hospital.com',
    '13800138003',
    '55555555-5555-5555-5555-555555555555',
    'nurse',
    '护士长',
    true
  )
ON CONFLICT (id) DO NOTHING;

-- 3. 创建示例医疗记录
-- =====================================================
INSERT INTO medical_records (
  id,
  record_number,
  patient_name,
  patient_id,
  patient_age,
  patient_gender,
  department_id,
  doctor_id,
  record_type,
  diagnosis_primary,
  diagnosis_secondary,
  content,
  content_sections,
  file_attachments,
  total_pages,
  word_count,
  status,
  priority_level,
  tags,
  metadata,
  created_by
)
VALUES 
  (
    '99999999-9999-9999-9999-999999999999',
    'MR20250829001',
    '张三',
    '110101199001011234',
    35,
    '男',
    '33333333-3333-3333-3333-333333333333',
    '66666666-6666-6666-6666-666666666666',
    'inpatient',
    '高血压',
    ARRAY['糖尿病', '冠心病'],
    '患者张三，男性，35岁，因"血压升高3个月"入院。患者3个月前体检发现血压升高，最高达160/100mmHg，伴有头晕、头痛症状。既往有糖尿病史2年，冠心病史1年。入院查体：血压155/95mmHg，心率78次/分，律齐。实验室检查：空腹血糖8.5mmol/L，糖化血红蛋白7.8%。心电图示：窦性心律，ST-T改变。',
    '{"主诉": "血压升高3个月", "现病史": "患者3个月前体检发现血压升高...", "既往史": "糖尿病史2年，冠心病史1年", "查体": "血压155/95mmHg，心率78次/分", "辅助检查": "空腹血糖8.5mmol/L"}'::jsonb,
    '[{"filename": "张三_入院记录.pdf", "size": 2048, "type": "application/pdf"}]'::jsonb,
    3,
    256,
    'completed',
    2,
    ARRAY['高血压', '糖尿病', '冠心病'],
    '{"source": "HIS系统", "import_method": "manual", "qc_checked": true}'::jsonb,
    '66666666-6666-6666-6666-666666666666'
  ),
  (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'MR20250829002',
    '李四',
    '110101199502021234',
    30,
    '女',
    '44444444-4444-4444-4444-444444444444',
    '77777777-7777-7777-7777-777777777777',
    'inpatient',
    '急性阑尾炎',
    NULL,
    '患者李四，女性，30岁，因"右下腹痛6小时"急诊入院。患者6小时前无明显诱因出现右下腹痛，呈持续性钝痛，伴恶心、呕吐。查体：右下腹压痛、反跳痛阳性，McBurney点压痛明显。血常规：WBC 12.5×10^9/L，中性粒细胞比例85%。腹部CT：阑尾壁增厚，周围脂肪间隙模糊。',
    '{"主诉": "右下腹痛6小时", "现病史": "患者6小时前无明显诱因出现右下腹痛...", "查体": "右下腹压痛、反跳痛阳性", "辅助检查": "WBC 12.5×10^9/L，腹部CT示阑尾炎"}'::jsonb,
    '[{"filename": "李四_急诊记录.pdf", "size": 1536, "type": "application/pdf"}]'::jsonb,
    2,
    189,
    'pending',
    3,
    ARRAY['急诊', '外科', '阑尾炎'],
    '{"source": "急诊系统", "import_method": "auto", "urgent": true}'::jsonb,
    '77777777-7777-7777-7777-777777777777'
  )
ON CONFLICT (id) DO NOTHING;

-- 4. 创建质控规则示例
-- =====================================================
INSERT INTO qc_rules (
  id,
  name,
  description,
  rule_config,
  is_active
)
VALUES 
  (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    '病历完整性检查',
    '检查病历是否包含必要的基本信息',
    '{
      "required_fields": ["patient_name", "patient_age", "diagnosis_primary"],
      "min_content_length": 50,
      "required_sections": ["主诉", "现病史", "查体"]
    }'::jsonb,
    true
  ),
  (
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    '诊断一致性检查',
    '检查主要诊断与病历内容的一致性',
    '{
      "check_diagnosis_content_match": true,
      "required_keywords": ["症状", "体征", "检查"],
      "severity_threshold": 0.8
    }'::jsonb,
    true
  )
ON CONFLICT (id) DO NOTHING;

-- 5. 创建质控结果示例
-- =====================================================
INSERT INTO qc_results (
  id,
  medical_record_id,
  rule_id,
  score,
  grade,
  issues,
  suggestions
)
VALUES 
  (
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    '99999999-9999-9999-9999-999999999999',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    85.5,
    'B',
    '[
      {"type": "warning", "message": "缺少过敏史记录", "severity": "medium"},
      {"type": "info", "message": "建议补充家族史", "severity": "low"}
    ]'::jsonb,
    '[
      {"category": "completeness", "suggestion": "建议补充患者过敏史信息"},
      {"category": "detail", "suggestion": "可以增加家族史相关内容"}
    ]'::jsonb
  ),
  (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    92.0,
    'A',
    '[
      {"type": "info", "message": "病历质量良好", "severity": "low"}
    ]'::jsonb,
    '[
      {"category": "quality", "suggestion": "病历记录规范，质量良好"}
    ]'::jsonb
  )
ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- 验证数据创建结果
-- =====================================================

-- 查看创建的部门
SELECT 
  id, 
  name, 
  code, 
  category,
  is_active
FROM departments 
ORDER BY sort_order;

-- 查看创建的用户
SELECT 
  id, 
  username, 
  full_name, 
  email,
  role_type,
  is_active
FROM user_profiles 
ORDER BY created_at;

-- 查看创建的医疗记录
SELECT 
  id, 
  record_number, 
  patient_name, 
  patient_age,
  diagnosis_primary,
  status,
  created_at
FROM medical_records 
ORDER BY created_at DESC;

-- 查看质控规则
SELECT 
  id, 
  name, 
  description,
  is_active
FROM qc_rules;

-- 查看质控结果
SELECT 
  qr.id,
  mr.patient_name,
  qru.name as rule_name,
  qr.score,
  qr.grade
FROM qc_results qr
JOIN medical_records mr ON qr.medical_record_id = mr.id
JOIN qc_rules qru ON qr.rule_id = qru.id;

-- =====================================================
-- 清理脚本（如需重置数据时使用）
-- =====================================================

/*
-- 注意：以下删除语句会清空测试数据，请谨慎使用

-- 删除质控结果
DELETE FROM qc_results WHERE id IN (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'
);

-- 删除质控规则
DELETE FROM qc_rules WHERE id IN (
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'cccccccc-cccc-cccc-cccc-cccccccccccc'
);

-- 删除医疗记录
DELETE FROM medical_records WHERE id IN (
  '99999999-9999-9999-9999-999999999999',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
);

-- 删除用户
DELETE FROM user_profiles WHERE id IN (
  '22222222-2222-2222-2222-222222222222',
  '66666666-6666-6666-6666-666666666666',
  '77777777-7777-7777-7777-777777777777',
  '88888888-8888-8888-8888-888888888888'
);

-- 删除部门
DELETE FROM departments WHERE id IN (
  '11111111-1111-1111-1111-111111111111',
  '33333333-3333-3333-3333-333333333333',
  '44444444-4444-4444-4444-444444444444',
  '55555555-5555-5555-5555-555555555555'
);
*/
