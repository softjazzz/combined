-- Reset and create unified rules data model (idempotent)
-- Safe note: only drops yibao_* business tables. Does not touch Supabase auth/system tables.
-- Run in Supabase SQL Editor or via CLI: supabase db push

begin;

-- 0) Drop existing yibao_* business objects (if any)
--    Drop TABLES first, then VIEWS to avoid type mismatch errors

-- tables
DROP TABLE IF EXISTS yibao_audit_results CASCADE;
DROP TABLE IF EXISTS yibao_audit_tasks CASCADE;
DROP TABLE IF EXISTS yibao_correction_suggestions CASCADE;
DROP TABLE IF EXISTS yibao_drug_age_rules CASCADE;
DROP TABLE IF EXISTS yibao_drug_duration_rules CASCADE;
DROP TABLE IF EXISTS yibao_drug_gender_rules CASCADE;
DROP TABLE IF EXISTS yibao_drug_hospital_level_rules CASCADE;
DROP TABLE IF EXISTS yibao_drug_visit_type_rules CASCADE;
DROP TABLE IF EXISTS yibao_rule_actions CASCADE;
DROP TABLE IF EXISTS yibao_rule_conditions CASCADE;
DROP TABLE IF EXISTS yibao_rule_triggers CASCADE;
DROP TABLE IF EXISTS yibao_rules CASCADE;
DROP TABLE IF EXISTS yibao_rule_categories CASCADE;
DROP TABLE IF EXISTS yibao_violations CASCADE;
DROP TABLE IF EXISTS yibao_drugs CASCADE;
DROP TABLE IF EXISTS yibao_medical_services CASCADE;

-- views (in case older environments created views with same names)
DROP VIEW IF EXISTS yibao_rule_statistics CASCADE;
DROP VIEW IF EXISTS yibao_drug_age_rules CASCADE;

-- 1) Types
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rule_severity') THEN
    CREATE TYPE rule_severity AS ENUM ('info','warn','block');
  END IF;
END $$;

-- 2) Categories
CREATE TABLE IF NOT EXISTS yibao_rule_categories (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3) Rules (unified)
CREATE TABLE IF NOT EXISTS yibao_rules (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  category_id BIGINT REFERENCES yibao_rule_categories(id),
  rule_type   TEXT NOT NULL,                 -- e.g. drug_age / drug_gender / visit_type / hospital_level / duration / surgery_pricing
  severity    rule_severity NOT NULL DEFAULT 'warn',
  enabled     BOOLEAN NOT NULL DEFAULT true,
  version     INT NOT NULL DEFAULT 1,
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_yibao_rules_type_enabled ON yibao_rules (rule_type, enabled);

-- 3.1) trigger to maintain updated_at
CREATE OR REPLACE FUNCTION yibao_set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_yibao_rules_updated_at ON yibao_rules;
CREATE TRIGGER trg_yibao_rules_updated_at BEFORE UPDATE ON yibao_rules
FOR EACH ROW EXECUTE PROCEDURE yibao_set_updated_at();

-- 4) Triggers/Conditions/Actions
CREATE TABLE IF NOT EXISTS yibao_rule_triggers (
  id          BIGSERIAL PRIMARY KEY,
  rule_id     BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
  event_type  TEXT NOT NULL                   -- e.g. order.drug.submit
);
CREATE INDEX IF NOT EXISTS idx_yibao_rule_triggers_event ON yibao_rule_triggers (event_type);

CREATE TABLE IF NOT EXISTS yibao_rule_conditions (
  id               BIGSERIAL PRIMARY KEY,
  rule_id          BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
  priority         INT NOT NULL DEFAULT 1,
  expression_json  JSONB NOT NULL            -- e.g. {"all": [{"fact":"patient.age","op":">","value":14}, ...]}
);
CREATE INDEX IF NOT EXISTS idx_yibao_rule_conditions_gin ON yibao_rule_conditions USING GIN (expression_json jsonb_path_ops);

CREATE TABLE IF NOT EXISTS yibao_rule_actions (
  id              BIGSERIAL PRIMARY KEY,
  rule_id         BIGINT REFERENCES yibao_rules(id) ON DELETE CASCADE,
  action_type     TEXT NOT NULL,             -- intercept / warn / notify
  message_template TEXT NOT NULL
);

-- 5) Master data (minimal)
CREATE TABLE IF NOT EXISTS yibao_drugs (
  drug_code   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  atc_code    TEXT,
  specs       JSONB NOT NULL DEFAULT '{}',
  metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS yibao_medical_services (
  service_code  TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  category      TEXT,
  metadata      JSONB NOT NULL DEFAULT '{}'
);

-- 6) Online violations & offline audit
CREATE TABLE IF NOT EXISTS yibao_violations (
  id          BIGSERIAL PRIMARY KEY,
  visit_id    TEXT NOT NULL,
  rule_id     BIGINT REFERENCES yibao_rules(id),
  severity    rule_severity NOT NULL,
  snapshot    JSONB NOT NULL,                -- context at hit time
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yibao_audit_tasks (
  id          BIGSERIAL PRIMARY KEY,
  rule_id     BIGINT REFERENCES yibao_rules(id),
  status      TEXT NOT NULL DEFAULT 'pending',
  payload     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yibao_audit_results (
  id          BIGSERIAL PRIMARY KEY,
  task_id     BIGINT REFERENCES yibao_audit_tasks(id) ON DELETE CASCADE,
  decision    TEXT NOT NULL,                 -- pass / fail / unclear
  detail      JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7) Compatibility view example
CREATE OR REPLACE VIEW yibao_rule_statistics AS
SELECT
  r.rule_type,
  COUNT(v.id) AS hits
FROM yibao_rules r
LEFT JOIN yibao_violations v ON v.rule_id = r.id
GROUP BY r.rule_type;

-- 8) Row Level Security (RLS)
-- Enable and add minimal policies: service_role full access; authenticated read-only; anon no access
ALTER TABLE yibao_rule_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_rule_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_drugs ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_medical_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_audit_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_audit_results ENABLE ROW LEVEL SECURITY;

-- read for authenticated & service_role
DO $$ BEGIN
  PERFORM 1;
  EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Apply the same simple policies to other tables
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'yibao_rule_categories','yibao_rule_triggers','yibao_rule_conditions','yibao_rule_actions',
    'yibao_drugs','yibao_medical_services','yibao_violations','yibao_audit_tasks','yibao_audit_results'
  ]) LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'public' AND tablename = t AND policyname = 'read_auth'
    ) THEN
      EXECUTE format(
        'CREATE POLICY read_auth ON %I FOR SELECT USING (auth.role() IN (''authenticated'',''service_role''))',
        t
      );
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname = 'public' AND tablename = t AND policyname = 'write_service'
    ) THEN
      EXECUTE format(
        'CREATE POLICY write_service ON %I FOR ALL USING (auth.role() = ''service_role'') WITH CHECK (auth.role() = ''service_role'')',
        t
      );
    END IF;
  END LOOP;
END $$;

commit;
