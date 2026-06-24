-- Step 3: Normalize check_logic.applicable_documents JSON array
-- Execute this after step 2 completes successfully

BEGIN;

-- First, let's see what we're working with
SELECT 'Before normalization - sample check_logic.applicable_documents:' as info;
SELECT
  rule_code,
  check_logic->'applicable_documents' as applicable_docs
FROM public.qc_rules
WHERE check_logic IS NOT NULL
  AND check_logic->'applicable_documents' IS NOT NULL
LIMIT 5;

-- Normalize check_logic.applicable_documents to use canonical codes
UPDATE public.qc_rules
SET check_logic = jsonb_set(
  COALESCE(check_logic, '{}'::jsonb),
  '{applicable_documents}',
  (
    SELECT to_jsonb(ARRAY(
      SELECT DISTINCT mapped_code FROM (
        SELECT CASE
          -- 忽略非标准类别
          WHEN doc_name IN ('急诊记录', '医嘱记录', '输血记录', '护理记录', '会诊记录') THEN NULL
          -- 直接映射常见中文名称
          WHEN doc_name = '入院记录' THEN 'admission_record'
          WHEN doc_name = '病程记录' THEN 'progress_note'
          WHEN doc_name = '出院记录' THEN 'discharge_record'
          WHEN doc_name IN ('手术记录', '手术相关记录') THEN 'operation_record'
          WHEN doc_name IN ('检查记录', '辅助检查') THEN 'examination_report'
          WHEN doc_name = '知情同意书' THEN 'consent_form'
          -- 保留已经是标准代码的值
          WHEN doc_name IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form') THEN doc_name
          -- 其他未知值忽略
          ELSE NULL
        END AS mapped_code
        FROM jsonb_array_elements_text(COALESCE(check_logic->'applicable_documents','[]'::jsonb)) AS doc_name
      ) mapping
      WHERE mapped_code IS NOT NULL
    ))::jsonb
  )
)
WHERE check_logic IS NOT NULL
  AND check_logic->'applicable_documents' IS NOT NULL;

COMMIT;

-- Verification of JSON normalization
SELECT 'JSON applicable_documents after normalization:' as info;
WITH json_elems AS (
  SELECT jsonb_array_elements_text(COALESCE(check_logic->'applicable_documents','[]'::jsonb)) AS v
  FROM public.qc_rules
  WHERE check_logic IS NOT NULL
    AND check_logic->'applicable_documents' IS NOT NULL
)
SELECT v AS json_value, COUNT(*) AS count
FROM json_elems
WHERE v IS NOT NULL AND v != ''
GROUP BY v
ORDER BY count DESC;
