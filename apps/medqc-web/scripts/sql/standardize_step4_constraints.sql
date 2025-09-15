-- Step 4: Add constraints and final verification
-- Execute this after step 3 completes successfully

BEGIN;

-- 1) Add CHECK constraints to enforce canonical values
ALTER TABLE public.qc_rules
  DROP CONSTRAINT IF EXISTS ck_qc_rules_primary_document_category,
  DROP CONSTRAINT IF EXISTS ck_qc_rules_document_categories;

ALTER TABLE public.qc_rules
  ADD CONSTRAINT ck_qc_rules_primary_document_category
    CHECK (primary_document_category IS NULL OR primary_document_category IN (
      'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
    )),
  ADD CONSTRAINT ck_qc_rules_document_categories
    CHECK (document_categories <@ ARRAY['admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form']);

COMMIT;

-- Final verification queries
SELECT 'FINAL VERIFICATION - All document categories should be canonical:' as info;

SELECT 'Primary document categories:' as category_type;
SELECT primary_document_category, COUNT(*) as count
FROM public.qc_rules
WHERE primary_document_category IS NOT NULL
GROUP BY primary_document_category
ORDER BY count DESC;

SELECT 'Document categories array:' as category_type;
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS category, COUNT(*) AS count
FROM elems
WHERE v IS NOT NULL AND v != ''
GROUP BY v
ORDER BY count DESC;

SELECT 'JSON applicable_documents:' as category_type;
WITH json_elems AS (
  SELECT jsonb_array_elements_text(COALESCE(check_logic->'applicable_documents','[]'::jsonb)) AS v
  FROM public.qc_rules
  WHERE check_logic::jsonb ? 'applicable_documents'
)
SELECT v AS json_value, COUNT(*) AS count
FROM json_elems
WHERE v IS NOT NULL AND v != ''
GROUP BY v
ORDER BY count DESC;

-- Check for any remaining non-canonical values (should be empty)
SELECT 'Non-canonical values found (should be empty):' as warning;
WITH all_cats AS (
  SELECT primary_document_category as cat FROM public.qc_rules WHERE primary_document_category IS NOT NULL
  UNION ALL
  SELECT unnest(document_categories) as cat FROM public.qc_rules WHERE document_categories IS NOT NULL
)
SELECT cat, COUNT(*) as count
FROM all_cats
WHERE cat NOT IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form')
GROUP BY cat
ORDER BY count DESC;
