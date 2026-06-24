-- Step 2: Normalize document categories
-- Execute this after step 1 completes successfully

BEGIN;

-- 1) Normalize document_categories array
UPDATE public.qc_rules q
SET document_categories = COALESCE(
  (
    SELECT ARRAY(
      SELECT DISTINCT x FROM (
        SELECT CASE
          WHEN a = '急诊记录' THEN 'admission_record'
          WHEN m.canonical_code IS NOT NULL THEN m.canonical_code
          WHEN a IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form') THEN a
          ELSE NULL
        END AS x
        FROM unnest(COALESCE(q.document_categories, '{}'::text[])) AS a
        LEFT JOIN public.document_category_alias m ON m.alias_text = a
      ) s
      WHERE x IS NOT NULL
    )
  ), '{}'::text[]
)
WHERE TRUE;

-- 2) Normalize primary_document_category
UPDATE public.qc_rules q
SET primary_document_category = COALESCE(
  m.canonical_code,
  CASE WHEN q.primary_document_category = '急诊记录' THEN 'admission_record' ELSE q.primary_document_category END
)
FROM public.document_category_alias m
WHERE q.primary_document_category = m.alias_text
   OR q.primary_document_category = '急诊记录';

COMMIT;

-- Verification after normalization
SELECT 'After normalization - Primary categories:' as info;
SELECT primary_document_category, COUNT(*) as count
FROM public.qc_rules
WHERE primary_document_category IS NOT NULL
GROUP BY primary_document_category
ORDER BY count DESC;

SELECT 'After normalization - Document categories:' as info;
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS category, COUNT(*) AS count
FROM elems
WHERE v IS NOT NULL AND v != ''
GROUP BY v
ORDER BY count DESC;
