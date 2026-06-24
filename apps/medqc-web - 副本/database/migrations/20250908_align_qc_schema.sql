-- Align QC schema with design detailed spec v2.0
-- Safe, idempotent migration for Supabase (PostgreSQL)

-- Dependencies
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 0) Ensure base tables exist (minimal definitions)
CREATE TABLE IF NOT EXISTS public.medical_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_number varchar(50) UNIQUE,
  record_name varchar(200),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.medical_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id uuid REFERENCES public.medical_records(id) ON DELETE CASCADE,
  document_type varchar(50) NOT NULL,
  title varchar(200) NOT NULL,
  content text NOT NULL,
  status varchar(20) DEFAULT 'active',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- 1) Enhance medical_documents with QC fields
ALTER TABLE public.medical_documents
  ADD COLUMN IF NOT EXISTS summary                text,
  ADD COLUMN IF NOT EXISTS position_info          jsonb,
  ADD COLUMN IF NOT EXISTS qc_status              varchar(20) DEFAULT 'pending' CHECK (qc_status IN ('pending','approved','rejected','reviewing','passed','warning','failed')),
  ADD COLUMN IF NOT EXISTS qc_score               numeric(5,2),
  ADD COLUMN IF NOT EXISTS qc_last_analyzed       timestamptz,
  ADD COLUMN IF NOT EXISTS qc_analysis_version    varchar(50),
  ADD COLUMN IF NOT EXISTS content_hash           varchar(64);

-- Useful indexes for QC queries
CREATE INDEX IF NOT EXISTS idx_medical_documents_qc_status        ON public.medical_documents(qc_status);
CREATE INDEX IF NOT EXISTS idx_medical_documents_qc_analyzed      ON public.medical_documents(qc_last_analyzed);
CREATE INDEX IF NOT EXISTS idx_medical_documents_qc_version       ON public.medical_documents(qc_analysis_version);
CREATE INDEX IF NOT EXISTS idx_medical_documents_content_hash     ON public.medical_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_medical_documents_position_info    ON public.medical_documents USING GIN (position_info);

-- 2) Document QC results table (new)
CREATE TABLE IF NOT EXISTS public.document_qc_results (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id           uuid NOT NULL REFERENCES public.medical_documents(id) ON DELETE CASCADE,
  template_id           uuid,
  rule_id               text NOT NULL,  -- string id for flexibility (can map to qc_rules/qc_rules_poc)

  -- QC outcome
  result_status         varchar(20) NOT NULL CHECK (result_status IN ('passed','failed','warning','error')),
  score                 numeric(5,2) DEFAULT 0,
  max_score             numeric(5,2) DEFAULT 100,
  confidence_score      numeric(3,2) CHECK (confidence_score BETWEEN 0 AND 1),

  -- Issue details
  issue_category        varchar(50),
  issue_description     text,
  evidence_text         text,
  evidence_location     jsonb,
  suggestions           text[],

  -- AI analysis details
  ai_reasoning          text,
  ai_model_used         varchar(100),
  analysis_time_ms      integer,

  -- Manual review
  manual_review_status  varchar(20) DEFAULT 'pending' CHECK (manual_review_status IN ('pending','confirmed','disputed','corrected')),
  manual_reviewer_id    uuid,
  manual_review_notes   text,
  manual_review_time    timestamptz,

  -- Timestamps
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

-- Indexes for QC results
CREATE INDEX IF NOT EXISTS idx_doc_qc_results_document_id ON public.document_qc_results(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_qc_results_rule_id     ON public.document_qc_results(rule_id);
CREATE INDEX IF NOT EXISTS idx_doc_qc_results_status      ON public.document_qc_results(result_status);
CREATE INDEX IF NOT EXISTS idx_doc_qc_results_created     ON public.document_qc_results(created_at);

-- 3) Update trigger helper (shared)
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to document_qc_results
DROP TRIGGER IF EXISTS trg_document_qc_results_updated_at ON public.document_qc_results;
CREATE TRIGGER trg_document_qc_results_updated_at
  BEFORE UPDATE ON public.document_qc_results
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 4) Hash function for content hashing (idempotent)
CREATE OR REPLACE FUNCTION public.calculate_content_hash(content text)
RETURNS text AS $$
BEGIN
  RETURN encode(digest(COALESCE(content, ''), 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 5) QC statistics view per medical record
CREATE OR REPLACE VIEW public.qc_statistics_view AS
SELECT
  d.record_id,
  COUNT(d.id)                                                   AS total_documents,
  COUNT(*) FILTER (WHERE d.qc_status = 'passed')                AS passed_count,
  COUNT(*) FILTER (WHERE d.qc_status = 'warning')               AS warning_count,
  COUNT(*) FILTER (WHERE d.qc_status = 'failed')                AS failed_count,
  COUNT(*) FILTER (WHERE d.qc_status = 'pending')               AS pending_count,
  ROUND(AVG(d.qc_score)::numeric, 2)                            AS avg_qc_score,
  MAX(d.qc_last_analyzed)                                       AS last_analyzed_time
FROM public.medical_documents d
WHERE d.status = 'active'
GROUP BY d.record_id;

-- 6) Convenience check messages (optional)
SELECT 'QC schema alignment complete' AS message;
SELECT 'medical_documents columns added (if missing)' AS message, COUNT(*) FROM information_schema.columns WHERE table_name='medical_documents';
SELECT 'document_qc_results exists' AS message, COUNT(*) FROM information_schema.tables WHERE table_name='document_qc_results';


