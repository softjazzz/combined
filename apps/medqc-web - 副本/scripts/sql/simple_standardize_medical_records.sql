-- 简化版：标准化测试病历数据中的文书分类
-- 请在Supabase SQL编辑器中分步执行

-- 步骤1：查看当前数据分布
SELECT 'Current data analysis:' as step;
SELECT 
  document_category,
  COUNT(*) as count
FROM public.medical_records_test
WHERE document_category IS NOT NULL
GROUP BY document_category
ORDER BY count DESC;

-- 步骤2：标准化document_category字段
UPDATE public.medical_records_test
SET document_category = CASE
  -- 病程记录相关
  WHEN document_category IN ('病程记录', '首次病程记录', '日常病程记录', '术后病程记录', '出院病程记录') 
    THEN 'progress_note'
  -- 入院记录相关  
  WHEN document_category IN ('入院记录', '入院病历', '入院评估') 
    THEN 'admission_record'
  -- 出院记录相关
  WHEN document_category IN ('出院记录', '出院小结', '出院总结') 
    THEN 'discharge_record'
  -- 手术相关记录
  WHEN document_category IN ('手术记录', '术前小结', '术前讨论记录', '手术同意书', '麻醉记录', '术前准备') 
    THEN 'operation_record'
  -- 辅助检查
  WHEN document_category IN ('检查记录', '检验报告', '影像报告', 'CT检查记录', '核磁检查记录', '实验室检查', '辅助检查') 
    THEN 'examination_report'
  -- 知情同意书
  WHEN document_category IN ('知情同意书', '手术同意书', '治疗同意书', '检查同意书') 
    THEN 'consent_form'
  -- 保留已经是标准代码的
  WHEN document_category IN ('admission_record', 'progress_note', 'discharge_record', 'operation_record', 'examination_report', 'consent_form')
    THEN document_category
  -- 其他未知类型暂时保持原样
  ELSE document_category
END
WHERE document_category IS NOT NULL;

-- 步骤3：验证标准化结果
SELECT 'After standardization:' as step;
SELECT 
  document_category,
  COUNT(*) as count
FROM public.medical_records_test
WHERE document_category IS NOT NULL
GROUP BY document_category
ORDER BY count DESC;
