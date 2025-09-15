-- Initialize document_category_config table with 6 standard categories
-- This will fix the frontend filter dropdown issue

BEGIN;

-- Create table if not exists
CREATE TABLE IF NOT EXISTS public.document_category_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_code TEXT NOT NULL UNIQUE,
  category_name TEXT NOT NULL,
  category_description TEXT,
  sort_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Clear existing data and insert 6 standard categories
DELETE FROM public.document_category_config;

INSERT INTO public.document_category_config (
  category_code, 
  category_name, 
  category_description, 
  sort_order, 
  is_active
) VALUES
  ('admission_record', '入院记录', '患者入院时的基本信息和诊断记录', 1, true),
  ('progress_note', '病程记录', '患者住院期间的病情变化和治疗过程记录', 2, true),
  ('discharge_record', '出院记录', '患者出院时的诊断、治疗总结和后续建议', 3, true),
  ('operation_record', '手术相关记录', '手术记录、麻醉记录等手术相关文档', 4, true),
  ('examination_report', '辅助检查', '实验室检查、影像学检查等辅助检查报告', 5, true),
  ('consent_form', '知情同意书', '各类医疗操作的知情同意文件', 6, true);

COMMIT;

-- Verify the data
SELECT 'Verification - document_category_config contents:' as info;
SELECT 
  category_code,
  category_name,
  category_description,
  sort_order,
  is_active
FROM public.document_category_config 
ORDER BY sort_order;
