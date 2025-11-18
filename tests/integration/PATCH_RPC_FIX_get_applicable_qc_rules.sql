-- Patch: disambiguate override_action reference in RPC function get_applicable_qc_rules
-- Reason: PostgREST 400 with error 42702: column reference "override_action" is ambiguous
-- Safe to run multiple times

CREATE OR REPLACE FUNCTION get_applicable_qc_rules(
    p_department_id UUID,
    p_document_type TEXT DEFAULT NULL,
    p_at TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
    id UUID,
    rule_code VARCHAR(50),
    name VARCHAR(200),
    description TEXT,
    category VARCHAR(50),
    rule_type VARCHAR(20),
    severity VARCHAR(20),
    check_logic JSONB,
    scoring_config JSONB,
    priority INTEGER,
    source VARCHAR(20),
    scope VARCHAR(20),
    department_id UUID,
    parent_rule_id UUID,
    override_action VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    WITH
    global_rules AS (
        SELECT
            r.id,
            r.rule_code,
            r.name,
            r.description,
            r.category,
            r.rule_type,
            r.severity,
            r.check_logic,
            r.scoring_config,
            r.priority,
            'global'::VARCHAR(20) AS source,
            r.scope,
            r.department_id,
            r.parent_rule_id,
            r.override_action
        FROM qc_rules r
        WHERE r.scope = 'global'
          AND r.is_active = true
          AND r.status = 'published'
          AND (r.effective_from IS NULL OR r.effective_from <= p_at)
          AND (r.effective_to IS NULL OR r.effective_to >= p_at)
          AND (
              p_document_type IS NULL
              OR r.applicable_documents IS NULL
              OR array_length(r.applicable_documents, 1) IS NULL
              OR array_length(r.applicable_documents, 1) = 0
              OR p_document_type = ANY(r.applicable_documents)
          )
    ),
    dept_rules AS (
        SELECT
            r.id,
            r.rule_code,
            r.name,
            r.description,
            r.category,
            r.rule_type,
            r.severity,
            r.check_logic,
            r.scoring_config,
            r.priority,
            'department'::VARCHAR(20) AS source,
            r.scope,
            r.department_id,
            r.parent_rule_id,
            r.override_action
        FROM qc_rules r
        WHERE r.scope = 'department'
          AND r.department_id = p_department_id
          AND r.is_active = true
          AND r.status = 'published'
          AND (r.effective_from IS NULL OR r.effective_from <= p_at)
          AND (r.effective_to IS NULL OR r.effective_to >= p_at)
          AND (
              p_document_type IS NULL
              OR r.applicable_documents IS NULL
              OR array_length(r.applicable_documents, 1) IS NULL
              OR array_length(r.applicable_documents, 1) = 0
              OR p_document_type = ANY(r.applicable_documents)
          )
    ),
    merged_rules AS (
        SELECT * FROM dept_rules dr WHERE dr.override_action = 'override'
        UNION ALL
        SELECT * FROM global_rules gr
        WHERE gr.rule_code NOT IN (
            SELECT dr.rule_code FROM dept_rules dr
            WHERE dr.override_action IN ('override', 'disable')
        )
    )
    SELECT
        m.id,
        m.rule_code,
        m.name,
        m.description,
        m.category,
        m.rule_type,
        m.severity,
        m.check_logic,
        m.scoring_config,
        m.priority,
        m.source,
        m.scope,
        m.department_id,
        m.parent_rule_id,
        m.override_action
    FROM merged_rules m
    ORDER BY m.priority DESC, m.rule_code ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_applicable_qc_rules(UUID, TEXT, TIMESTAMPTZ) IS '获取适用于指定科室和文书类型的质控规则，自动处理规则覆盖和禁用逻辑 (已修复 override_action 歧义)';

