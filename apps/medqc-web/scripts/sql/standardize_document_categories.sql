-- Plan A: Standardize all document categories to 6 canonical types
-- Safe migration script for Supabase (run in SQL editor)
-- This script:
--  1) Creates alias mapping table (idempotent)
--  2) Backups qc_rules
--  3) Previews current non-canonical values
--  4) Normalizes qc_rules.document_categories and primary_document_category
--  5) (Optional) Normalizes check_logic.applicable_documents to canonical codes
--  6) Adds CHECK constraint to enforce 6 canonical values
--  7) Provides verification queries

BEGIN;

-- 1) Alias mapping table (non-standard zh names -> canonical code)
CREATE TABLE IF NOT EXISTS public.document_category_alias (
  alias_text TEXT PRIMARY KEY,
  canonical_code TEXT NOT NULL CHECK (canonical_code IN (
    'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
  ))
);

-- Upsert alias mappings (note: 不再为“急诊记录”建立别名，避免其再次进入系统)
INSERT INTO public.document_category_alias(alias_text, canonical_code) VALUES
  ('手术记录','operation_record'),
  ('检查记录','examination_report'),
  ('输血记录','progress_note'),
  ('治疗记录','progress_note'),
  ('医嘱记录','progress_note')
ON CONFLICT (alias_text) DO UPDATE SET canonical_code = EXCLUDED.canonical_code;

-- 显式移除别名表中的“急诊记录”（如存在）
DELETE FROM public.document_category_alias WHERE alias_text = '急诊记录';

-- 2) Backup qc_rules
CREATE TABLE IF NOT EXISTS public.qc_rules_backup_before_standardize AS
SELECT * FROM public.qc_rules;

-- 3) Preview: unknown values inside document_categories (before update)
--    Values that are neither canonical codes nor known aliases
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS unknown_value, COUNT(*) AS cnt
FROM elems
WHERE v NOT IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form')
  AND v NOT IN (SELECT alias_text FROM public.document_category_alias)
GROUP BY v
ORDER BY cnt DESC;

-- 3b) Preview: values inside check_logic.applicable_documents (before update)
WITH json_elems AS (
  SELECT jsonb_array_elements_text(COALESCE(check_logic->'applicable_documents','[]'::jsonb)) AS v
  FROM public.qc_rules
)
SELECT v AS json_value, COUNT(*) AS cnt
FROM json_elems
GROUP BY v
ORDER BY cnt DESC;

-- 4a) Normalize qc_rules.document_categories (array)
--     - Map aliases to canonical codes
--     - Remove '急诊记录' alias (mapped to 'admission_record')
--     - Keep only canonical codes
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

-- 4b) Normalize primary_document_category (scalar)
UPDATE public.qc_rules q
SET primary_document_category = COALESCE(
  m.canonical_code,
  CASE WHEN q.primary_document_category = '急诊记录' THEN 'admission_record' ELSE q.primary_document_category END
)
FROM public.document_category_alias m
WHERE q.primary_document_category = m.alias_text
   OR q.primary_document_category = '急诊记录';

-- 5) Normalize check_logic.applicable_documents (JSON array)
--    Converts Chinese names/aliases to canonical codes and removes non-standard values (incl. 急诊记录).
UPDATE public.qc_rules q
SET check_logic = jsonb_set(
  COALESCE(q.check_logic, '{}'::jsonb),
  '{applicable_documents}',
  COALESCE((
    SELECT to_jsonb(ARRAY(
      SELECT DISTINCT y FROM (
        SELECT CASE
          WHEN e = '急诊记录' THEN NULL
          WHEN am.canonical_code IS NOT NULL THEN am.canonical_code
          WHEN e IN ('入院记录','病程记录','出院记录','手术记录','检查记录','知情同意书') THEN (
            CASE e
              WHEN '入院记录' THEN 'admission_record'
              WHEN '病程记录' THEN 'progress_note'
              WHEN '出院记录' THEN 'discharge_record'
              WHEN '手术记录' THEN 'operation_record'
              WHEN '检查记录' THEN 'examination_report'
              WHEN '知情同意书' THEN 'consent_form'
            END)
          WHEN e IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form') THEN e
          ELSE NULL
        END AS y
        FROM jsonb_array_elements_text(COALESCE(q.check_logic->'applicable_documents','[]'::jsonb)) AS e
        LEFT JOIN public.document_category_alias am ON am.alias_text = e
      ) tmp
      WHERE y IS NOT NULL
    ))::jsonb,
    '[]'::jsonb
  )
)
WHERE q.check_logic::jsonb ? 'applicable_documents';

-- 6) Enforce canonical set via CHECK constraint
ALTER TABLE public.qc_rules
  DROP CONSTRAINT IF EXISTS ck_qc_rules_primary_document_category,
  ADD CONSTRAINT ck_qc_rules_primary_document_category
  CHECK (
    primary_document_category IS NULL
    OR primary_document_category IN (
      'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
    )
  );

COMMIT;

-- 7) Verification queries (run after COMMIT)
-- A) Primary category distribution
SELECT primary_document_category, COUNT(*)
FROM public.qc_rules
GROUP BY primary_document_category
ORDER BY COUNT(*) DESC;

-- B) document_categories flattened distribution
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS category, COUNT(*) AS cnt
FROM elems
GROUP BY v
ORDER BY cnt DESC;

-- C) Residual unknowns in document_categories (should be zero rows)
WITH elems AS (
  SELECT unnest(COALESCE(document_categories, '{}')) AS v FROM public.qc_rules
)
SELECT v AS unknown_value, COUNT(*) AS cnt
FROM elems
WHERE v NOT IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form')
GROUP BY v
ORDER BY cnt DESC;

-- D) Residual non-canonical values in check_logic.applicable_documents (should be zero rows)
WITH json_elems AS (
  SELECT jsonb_array_elements_text(COALESCE(check_logic->'applicable_documents','[]'::jsonb)) AS v
  FROM public.qc_rules
)
SELECT v AS json_value, COUNT(*) AS cnt
FROM json_elems
WHERE v NOT IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form')
GROUP BY v
ORDER BY cnt DESC;

-- E) Preview of document_category_config table for non-canonical codes (should be zero rows)
SELECT category_code, category_name
FROM public.document_category_config
WHERE is_active = true
  AND category_code NOT IN ('admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form')
ORDER BY category_code;

