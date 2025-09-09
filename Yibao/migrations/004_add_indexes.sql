-- Add high-value indexes for violations table
CREATE INDEX IF NOT EXISTS idx_yibao_violations_created_at ON public.yibao_violations (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_yibao_violations_rule_id ON public.yibao_violations (rule_id);
CREATE INDEX IF NOT EXISTS idx_yibao_violations_severity ON public.yibao_violations (severity);

-- Optional composite index when pagination + filter frequently combine
-- CREATE INDEX IF NOT EXISTS idx_yibao_violations_rule_created ON public.yibao_violations (rule_id, created_at DESC);





