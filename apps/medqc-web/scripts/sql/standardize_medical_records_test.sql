-- 标准化测试病历数据中的文书分类
-- 将现有的中文分类名称映射到6个标准英文代码

-- 1. 查看当前文书分类的分布情况
SELECT 'Current document categories distribution:' as info;
SELECT
  document_category,
  COUNT(*) as count
FROM public.medical_records_test
WHERE document_category IS NOT NULL
GROUP BY document_category
ORDER BY count DESC;

-- 2. 查看documents字段中的文书类型分布
SELECT 'Current documents field analysis:' as info;
WITH doc_analysis AS (
  SELECT
    id,
    document_category,
    jsonb_array_elements_text(documents::jsonb) as doc_type
  FROM public.medical_records_test
  WHERE documents IS NOT NULL
    AND documents != ''
    AND documents != 'null'
    AND jsonb_typeof(documents::jsonb) = 'array'
)
SELECT
  doc_type,
  COUNT(*) as count
FROM doc_analysis
WHERE doc_type IS NOT NULL
GROUP BY doc_type
ORDER BY count DESC
LIMIT 20;

-- 3. 标准化document_category字段
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

-- 4. 标准化documents字段中的文书类型
UPDATE public.medical_records_test
SET documents = (
  SELECT jsonb_agg(
    CASE
      -- 病程记录相关
      WHEN doc_item->>'type' IN ('病程记录', '首次病程记录', '日常病程记录', '术后病程记录')
        THEN jsonb_set(doc_item, '{type}', '"progress_note"')
      -- 入院记录相关
      WHEN doc_item->>'type' IN ('入院记录', '入院病历', '入院评估')
        THEN jsonb_set(doc_item, '{type}', '"admission_record"')
      -- 出院记录相关
      WHEN doc_item->>'type' IN ('出院记录', '出院小结', '出院总结')
        THEN jsonb_set(doc_item, '{type}', '"discharge_record"')
      -- 手术相关记录
      WHEN doc_item->>'type' IN ('手术记录', '术前小结', '术前讨论记录', '麻醉记录')
        THEN jsonb_set(doc_item, '{type}', '"operation_record"')
      -- 辅助检查
      WHEN doc_item->>'type' IN ('检查记录', '检验报告', '影像报告', 'CT检查记录', '核磁检查记录')
        THEN jsonb_set(doc_item, '{type}', '"examination_report"')
      -- 知情同意书
      WHEN doc_item->>'type' IN ('知情同意书', '手术同意书', '治疗同意书')
        THEN jsonb_set(doc_item, '{type}', '"consent_form"')
      -- 保留已经是标准代码的
      ELSE doc_item
    END
  )
  FROM jsonb_array_elements(documents::jsonb) as doc_item
)
WHERE documents IS NOT NULL
  AND documents != ''
  AND documents != 'null'
  AND jsonb_typeof(documents::jsonb) = 'array';

-- 5. 验证标准化结果
SELECT 'Standardization results for document_category:' as info;
SELECT
  document_category,
  COUNT(*) as count
FROM public.medical_records_test
WHERE document_category IS NOT NULL
GROUP BY document_category
ORDER BY count DESC;

-- 6. 验证documents字段标准化结果
SELECT 'Standardization results for documents field:' as info;
WITH doc_analysis AS (
  SELECT
    jsonb_array_elements_text(jsonb_path_query_array(documents::jsonb, '$[*].type')) as doc_type
  FROM public.medical_records_test
  WHERE documents IS NOT NULL
    AND documents != ''
    AND documents != 'null'
    AND jsonb_typeof(documents::jsonb) = 'array'
)
SELECT
  doc_type,
  COUNT(*) as count
FROM doc_analysis
WHERE doc_type IS NOT NULL
GROUP BY doc_type
ORDER BY count DESC;
