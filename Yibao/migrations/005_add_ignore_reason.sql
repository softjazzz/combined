-- Add ignore reasons fields to violations
ALTER TABLE public.yibao_violations
  ADD COLUMN IF NOT EXISTS ignore_reason text,
  ADD COLUMN IF NOT EXISTS ignore_note text;




