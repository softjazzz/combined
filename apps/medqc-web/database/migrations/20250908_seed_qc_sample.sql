-- Seed a minimal QC dataset to verify new schema and views

-- 1) Compute content_hash for existing documents if missing
UPDATE public.medical_documents
SET content_hash = public.calculate_content_hash(content)
WHERE content_hash IS NULL AND content IS NOT NULL;

-- 2) Set QC fields for one sample document (admission_record)
WITH target_doc AS (
  SELECT md.id
  FROM public.medical_documents md
  JOIN public.medical_records mr ON md.record_id = mr.id
  WHERE mr.record_number = 'MR20240827001' AND md.document_type = 'admission_record'
  LIMIT 1
)
UPDATE public.medical_documents d
SET
  qc_status = 'warning',
  qc_score = 72.50,
  qc_last_analyzed = NOW(),
  qc_analysis_version = '1.0'
FROM target_doc t
WHERE d.id = t.id;

-- 3) Insert one QC result row for that document
INSERT INTO public.document_qc_results (
  document_id,
  template_id,
  rule_id,
  result_status,
  score,
  max_score,
  confidence_score,
  issue_category,
  issue_description,
  evidence_text,
  evidence_location,
  suggestions,
  ai_reasoning,
  ai_model_used,
  analysis_time_ms
)
SELECT
  d.id,
  NULL::uuid,
  'POC_001',
  'failed',
  0.00,
  100.00,
  0.85,
  '完整性',
  '入院记录缺少入院诊断时间字段',
  '未找到“入院诊断时间”片段',
  jsonb_build_object('section','admission_record','hint','诊断时间'),
  ARRAY['补充“入院诊断时间”','校对入院诊断条目'],
  '模型根据上下文判断缺失关键字段',
  COALESCE(m.model_name, 'mock'),
  1200
FROM public.medical_documents d
JOIN public.medical_records r ON d.record_id = r.id
LEFT JOIN public.llm_api_providers p ON p.provider_code = 'mock'
LEFT JOIN public.llm_models m ON m.provider_id = p.id AND m.model_code = 'mock'
WHERE r.record_number = 'MR20240827001' AND d.document_type = 'admission_record'
ON CONFLICT DO NOTHING;

-- 4) Quick checks
SELECT 'QC sample seeded' AS message,
       (SELECT COUNT(*) FROM public.document_qc_results) AS qc_results_count,
       (SELECT COUNT(*) FROM public.medical_documents WHERE qc_status IS NOT NULL) AS qc_docs_with_status;


