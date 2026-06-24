-- Step 1: Setup alias mapping table and backup
-- Execute this first in Supabase SQL editor

BEGIN;

-- 1) Create alias mapping table
CREATE TABLE IF NOT EXISTS public.document_category_alias (
  alias_text TEXT PRIMARY KEY,
  canonical_code TEXT NOT NULL CHECK (canonical_code IN (
    'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
  ))
);

-- 2) Insert alias mappings
INSERT INTO public.document_category_alias(alias_text, canonical_code) VALUES
  ('手术记录','operation_record'),
  ('检查记录','examination_report'),
  ('输血记录','progress_note'),
  ('治疗记录','progress_note'),
  ('医嘱记录','progress_note'),
  ('病程记录','progress_note'),
  ('入院记录','admission_record'),
  ('出院记录','discharge_record'),
  ('知情同意书','consent_form')
ON CONFLICT (alias_text) DO UPDATE SET canonical_code = EXCLUDED.canonical_code;

-- 3) Remove emergency record alias
DELETE FROM public.document_category_alias WHERE alias_text = '急诊记录';

-- 4) Create backup table
DROP TABLE IF EXISTS public.qc_rules_backup_before_standardize;
CREATE TABLE public.qc_rules_backup_before_standardize AS
SELECT * FROM public.qc_rules;

COMMIT;

-- 5) Preview current data before changes
SELECT 'Primary document categories:' as info;
SELECT primary_document_category, COUNT(*) as count
FROM public.qc_rules
WHERE primary_document_category IS NOT NULL
GROUP BY primary_document_category
ORDER BY count DESC;

SELECT 'Document categories array:' as info;
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS category, COUNT(*) AS count
FROM elems
WHERE v IS NOT NULL
GROUP BY v
ORDER BY count DESC;
