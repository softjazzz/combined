-- 009_department_qc_rules.sql
-- 科室级质控规则配置功能
-- 
-- 功能概述：
-- 1. 扩展 qc_rules 表，支持科室级规则配置
-- 2. 支持规则版本管理和生效期控制
-- 3. 支持规则覆盖和禁用机制
-- 4. 创建规则变更审计日志表
-- 5. 创建 RPC 函数统一规则匹配逻辑
--
-- 相关文档：
-- - PRD: docs/PRD_DEPARTMENT_QC_RULES.md
-- - 变更日志: docs/PRD_DEPARTMENT_QC_RULES_CHANGELOG.md
--
-- 版本: 2.0
-- 创建日期: 2025-10-12

-- ============================================================================
-- 步骤 0: 预检查和备份
-- ============================================================================

-- 输出迁移开始信息
DO $$
BEGIN
    RAISE NOTICE '=== Starting Migration 009: Department QC Rules ===';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

-- 检查 qc_rules 表是否存在
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'qc_rules'
    ) THEN
        RAISE EXCEPTION 'qc_rules table does not exist. Please run previous migrations first.';
    END IF;
    
    RAISE NOTICE '✓ qc_rules table exists';
END $$;

-- 检查 departments 表是否存在，如果不存在则创建
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'departments'
    ) THEN
        RAISE NOTICE 'Creating departments table...';
        
        CREATE TABLE departments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            parent_id UUID REFERENCES departments(id),
            level INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- 创建索引
        CREATE INDEX idx_departments_parent ON departments(parent_id);
        CREATE INDEX idx_departments_active ON departments(is_active);
        
        -- 插入示例科室数据
        INSERT INTO departments (code, name, description) VALUES
        ('DEPT_001', '内科', '内科科室'),
        ('DEPT_002', '外科', '外科科室'),
        ('DEPT_003', '儿科', '儿科科室'),
        ('DEPT_004', '急诊科', '急诊科室'),
        ('DEPT_005', 'ICU', '重症监护室'),
        ('DEPT_006', '骨科', '骨科科室'),
        ('DEPT_007', '神经内科', '神经内科科室'),
        ('DEPT_008', '心内科', '心内科科室');
        
        RAISE NOTICE '✓ Created departments table with sample data';
    ELSE
        RAISE NOTICE '✓ departments table already exists';
    END IF;
END $$;

-- ============================================================================
-- 步骤 1: 扩展 qc_rules 表
-- ============================================================================

RAISE NOTICE 'Step 1: Extending qc_rules table...';

-- 1.1 添加规则范围和科室字段
DO $$
BEGIN
    -- scope: 规则范围 (global/department)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'scope'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN scope VARCHAR(20) DEFAULT 'global' 
        CHECK (scope IN ('global', 'department'));
        
        RAISE NOTICE '✓ Added scope column';
    END IF;
    
    -- department_id: 科室ID（仅科室规则）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'department_id'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN department_id UUID REFERENCES departments(id);
        
        RAISE NOTICE '✓ Added department_id column';
    END IF;
    
    -- parent_rule_id: 父规则ID（覆盖规则时使用）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'parent_rule_id'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN parent_rule_id UUID REFERENCES qc_rules(id);
        
        RAISE NOTICE '✓ Added parent_rule_id column';
    END IF;
END $$;

-- 1.2 添加覆盖配置字段
DO $$
BEGIN
    -- override_action: 覆盖行为 (override/disable)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'override_action'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN override_action VARCHAR(20) DEFAULT 'override'
        CHECK (override_action IN ('override', 'disable'));
        
        RAISE NOTICE '✓ Added override_action column';
    END IF;
    
    -- override_config: 覆盖配置（记录哪些字段被覆盖）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'override_config'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN override_config JSONB DEFAULT '{}';
        
        RAISE NOTICE '✓ Added override_config column';
    END IF;
    
    -- priority: 优先级（数字越大优先级越高）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'priority'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN priority INTEGER DEFAULT 0;
        
        RAISE NOTICE '✓ Added priority column';
    END IF;
END $$;

-- 1.3 添加版本和生效期字段
DO $$
BEGIN
    -- status: 规则状态 (draft/published/archived)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'status'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN status VARCHAR(20) DEFAULT 'published'
        CHECK (status IN ('draft', 'published', 'archived'));
        
        RAISE NOTICE '✓ Added status column';
    END IF;
    
    -- effective_from: 生效开始时间
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'effective_from'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN effective_from TIMESTAMPTZ;
        
        RAISE NOTICE '✓ Added effective_from column';
    END IF;
    
    -- effective_to: 生效结束时间
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'effective_to'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN effective_to TIMESTAMPTZ;
        
        RAISE NOTICE '✓ Added effective_to column';
    END IF;
END $$;

-- 1.4 添加审核信息字段
DO $$
BEGIN
    -- approved_by: 审核人ID
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'approved_by'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN approved_by UUID;
        
        RAISE NOTICE '✓ Added approved_by column';
    END IF;
    
    -- approved_at: 审核时间
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'approved_at'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN approved_at TIMESTAMPTZ;
        
        RAISE NOTICE '✓ Added approved_at column';
    END IF;
END $$;

-- 1.5 更新现有数据
DO $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    -- 将现有规则设置为全局规则
    UPDATE qc_rules 
    SET scope = 'global',
        status = CASE 
            WHEN is_active = true THEN 'published'
            ELSE 'archived'
        END
    WHERE scope IS NULL;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    RAISE NOTICE '✓ Updated % existing rules to global scope', updated_count;
END $$;

-- ============================================================================
-- 步骤 2: 添加约束和索引
-- ============================================================================

RAISE NOTICE 'Step 2: Adding constraints and indexes...';

-- 2.1 添加约束
DO $$
BEGIN
    -- 确保科室规则必须关联科室
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'chk_department_scope'
    ) THEN
        ALTER TABLE qc_rules 
        ADD CONSTRAINT chk_department_scope 
        CHECK (
            (scope = 'global' AND department_id IS NULL) OR
            (scope = 'department' AND department_id IS NOT NULL)
        );
        
        RAISE NOTICE '✓ Added chk_department_scope constraint';
    END IF;
END $$;

-- 2.2 创建唯一索引
DO $$
BEGIN
    -- 同科室同规则编号的已发布规则唯一
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'uk_dept_rule_code_published'
    ) THEN
        CREATE UNIQUE INDEX uk_dept_rule_code_published
        ON qc_rules(department_id, rule_code)
        WHERE scope = 'department' AND status = 'published';
        
        RAISE NOTICE '✓ Created uk_dept_rule_code_published index';
    END IF;
END $$;

-- 2.3 创建普通索引
DO $$
BEGIN
    -- scope 索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_scope') THEN
        CREATE INDEX idx_qc_rules_scope ON qc_rules(scope);
        RAISE NOTICE '✓ Created idx_qc_rules_scope index';
    END IF;
    
    -- department_id 索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_department') THEN
        CREATE INDEX idx_qc_rules_department ON qc_rules(department_id);
        RAISE NOTICE '✓ Created idx_qc_rules_department index';
    END IF;
    
    -- parent_rule_id 索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_parent') THEN
        CREATE INDEX idx_qc_rules_parent ON qc_rules(parent_rule_id);
        RAISE NOTICE '✓ Created idx_qc_rules_parent index';
    END IF;
    
    -- status 索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_status') THEN
        CREATE INDEX idx_qc_rules_status ON qc_rules(status);
        RAISE NOTICE '✓ Created idx_qc_rules_status index';
    END IF;
    
    -- effective 索引
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_effective') THEN
        CREATE INDEX idx_qc_rules_effective ON qc_rules(effective_from, effective_to);
        RAISE NOTICE '✓ Created idx_qc_rules_effective index';
    END IF;
    
    -- 复合索引（优化规则匹配查询）
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qc_rules_composite') THEN
        CREATE INDEX idx_qc_rules_composite 
        ON qc_rules(scope, department_id, is_active, status, effective_from, effective_to);
        RAISE NOTICE '✓ Created idx_qc_rules_composite index';
    END IF;
END $$;

-- 添加列注释
COMMENT ON COLUMN qc_rules.scope IS '规则范围: global（全局规则）/ department（科室规则）';
COMMENT ON COLUMN qc_rules.department_id IS '科室ID（仅科室规则）';
COMMENT ON COLUMN qc_rules.parent_rule_id IS '父规则ID（覆盖规则时使用）';
COMMENT ON COLUMN qc_rules.override_action IS '覆盖行为: override（覆盖配置）/ disable（禁用全局规则）';
COMMENT ON COLUMN qc_rules.override_config IS '覆盖配置（记录哪些字段被覆盖）';
COMMENT ON COLUMN qc_rules.priority IS '优先级（数字越大优先级越高）';
COMMENT ON COLUMN qc_rules.status IS '规则状态: draft（草稿）/ published（已发布）/ archived（已归档）';
COMMENT ON COLUMN qc_rules.effective_from IS '生效开始时间（可选）';
COMMENT ON COLUMN qc_rules.effective_to IS '生效结束时间（可选）';
COMMENT ON COLUMN qc_rules.approved_by IS '审核人ID';
COMMENT ON COLUMN qc_rules.approved_at IS '审核时间';

RAISE NOTICE '✓ Step 2 completed';

-- ============================================================================
-- 步骤 3: 创建规则变更审计日志表
-- ============================================================================

RAISE NOTICE 'Step 3: Creating qc_rule_change_logs table...';

CREATE TABLE IF NOT EXISTS qc_rule_change_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES qc_rules(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id),
    action VARCHAR(20) NOT NULL CHECK (action IN ('create', 'update', 'delete', 'enable', 'disable', 'publish', 'archive')),

    -- 变更内容
    old_values JSONB,
    new_values JSONB,
    diff JSONB,

    -- 操作人信息
    actor_id UUID NOT NULL,
    actor_name VARCHAR(200),
    actor_role VARCHAR(50),

    -- 变更原因
    reason TEXT,

    -- 审计信息
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_rule_change_logs_rule ON qc_rule_change_logs(rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_change_logs_department ON qc_rule_change_logs(department_id);
CREATE INDEX IF NOT EXISTS idx_rule_change_logs_actor ON qc_rule_change_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_rule_change_logs_action ON qc_rule_change_logs(action);
CREATE INDEX IF NOT EXISTS idx_rule_change_logs_created ON qc_rule_change_logs(created_at DESC);

-- 添加表注释
COMMENT ON TABLE qc_rule_change_logs IS '质控规则变更审计日志表';
COMMENT ON COLUMN qc_rule_change_logs.action IS '操作类型: create/update/delete/enable/disable/publish/archive';
COMMENT ON COLUMN qc_rule_change_logs.old_values IS '变更前的值';
COMMENT ON COLUMN qc_rule_change_logs.new_values IS '变更后的值';
COMMENT ON COLUMN qc_rule_change_logs.diff IS '差异对比';

RAISE NOTICE '✓ Created qc_rule_change_logs table';

-- ============================================================================
-- 步骤 4: 创建触发器函数（自动记录规则变更）
-- ============================================================================

RAISE NOTICE 'Step 4: Creating trigger function...';

CREATE OR REPLACE FUNCTION log_qc_rule_changes()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_id UUID;
    v_action VARCHAR(20);
BEGIN
    -- 获取当前用户ID（从应用层传入或使用系统用户）
    v_actor_id := COALESCE(current_setting('app.current_user_id', true)::UUID, '00000000-0000-0000-0000-000000000000'::UUID);

    IF TG_OP = 'INSERT' THEN
        v_action := 'create';
        INSERT INTO qc_rule_change_logs (
            rule_id,
            department_id,
            action,
            new_values,
            actor_id
        ) VALUES (
            NEW.id,
            NEW.department_id,
            v_action,
            to_jsonb(NEW),
            v_actor_id
        );
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        -- 判断具体的更新类型
        IF OLD.is_active = false AND NEW.is_active = true THEN
            v_action := 'enable';
        ELSIF OLD.is_active = true AND NEW.is_active = false THEN
            v_action := 'disable';
        ELSIF OLD.status != NEW.status AND NEW.status = 'published' THEN
            v_action := 'publish';
        ELSIF OLD.status != NEW.status AND NEW.status = 'archived' THEN
            v_action := 'archive';
        ELSE
            v_action := 'update';
        END IF;

        INSERT INTO qc_rule_change_logs (
            rule_id,
            department_id,
            action,
            old_values,
            new_values,
            actor_id
        ) VALUES (
            NEW.id,
            NEW.department_id,
            v_action,
            to_jsonb(OLD),
            to_jsonb(NEW),
            v_actor_id
        );
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        v_action := 'delete';
        INSERT INTO qc_rule_change_logs (
            rule_id,
            department_id,
            action,
            old_values,
            actor_id
        ) VALUES (
            OLD.id,
            OLD.department_id,
            v_action,
            to_jsonb(OLD),
            v_actor_id
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
DROP TRIGGER IF EXISTS trigger_log_qc_rule_changes ON qc_rules;
CREATE TRIGGER trigger_log_qc_rule_changes
AFTER INSERT OR UPDATE OR DELETE ON qc_rules
FOR EACH ROW EXECUTE FUNCTION log_qc_rule_changes();

RAISE NOTICE '✓ Created trigger function and trigger';

-- ============================================================================
-- 步骤 5: 创建 RPC 函数（获取适用的质控规则）
-- ============================================================================

RAISE NOTICE 'Step 5: Creating get_applicable_qc_rules RPC function...';

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
    -- 1. 获取有效的全局规则
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
    -- 2. 获取有效的科室规则
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
    -- 3. 合并规则（科室规则覆盖全局规则）
    merged_rules AS (
        -- 科室规则（覆盖类型）
        SELECT * FROM dept_rules WHERE override_action = 'override'
        UNION ALL
        -- 全局规则（排除被科室规则覆盖或禁用的）
        SELECT * FROM global_rules
        WHERE rule_code NOT IN (
            SELECT rule_code FROM dept_rules
            WHERE override_action IN ('override', 'disable')
        )
    )
    -- 4. 返回结果，按优先级排序
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

-- 添加函数注释
COMMENT ON FUNCTION get_applicable_qc_rules(UUID, TEXT, TIMESTAMPTZ) IS '获取适用于指定科室和文书类型的质控规则，自动处理规则覆盖和禁用逻辑';

RAISE NOTICE '✓ Created get_applicable_qc_rules RPC function';

-- ============================================================================
-- 步骤 6: 创建辅助视图和函数
-- ============================================================================

RAISE NOTICE 'Step 6: Creating helper views and functions...';

-- 6.1 创建规则统计视图
CREATE OR REPLACE VIEW qc_rules_department_statistics AS
SELECT
    -- 总规则数
    COUNT(*) AS total_rules,
    COUNT(*) FILTER (WHERE scope = 'global') AS global_rules,
    COUNT(*) FILTER (WHERE scope = 'department') AS department_rules,

    -- 按状态统计
    COUNT(*) FILTER (WHERE status = 'published') AS published_rules,
    COUNT(*) FILTER (WHERE status = 'draft') AS draft_rules,
    COUNT(*) FILTER (WHERE status = 'archived') AS archived_rules,

    -- 按激活状态统计
    COUNT(*) FILTER (WHERE is_active = true) AS active_rules,
    COUNT(*) FILTER (WHERE is_active = false) AS inactive_rules,

    -- 覆盖和禁用规则
    COUNT(*) FILTER (WHERE override_action = 'override' AND scope = 'department') AS override_rules,
    COUNT(*) FILTER (WHERE override_action = 'disable' AND scope = 'department') AS disabled_rules
FROM qc_rules;

COMMENT ON VIEW qc_rules_department_statistics IS '质控规则统计视图（包含科室规则）';

-- 6.2 创建按科室统计规则的视图
CREATE OR REPLACE VIEW qc_rules_by_department AS
SELECT
    d.id AS department_id,
    d.code AS department_code,
    d.name AS department_name,
    COUNT(r.id) AS rule_count,
    COUNT(r.id) FILTER (WHERE r.status = 'published') AS published_count,
    COUNT(r.id) FILTER (WHERE r.override_action = 'override') AS override_count,
    COUNT(r.id) FILTER (WHERE r.override_action = 'disable') AS disable_count,
    array_agg(r.rule_code ORDER BY r.rule_code) FILTER (WHERE r.id IS NOT NULL) AS rule_codes
FROM departments d
LEFT JOIN qc_rules r ON r.department_id = d.id AND r.scope = 'department'
WHERE d.is_active = true
GROUP BY d.id, d.code, d.name
ORDER BY rule_count DESC;

COMMENT ON VIEW qc_rules_by_department IS '按科室统计规则数量';

RAISE NOTICE '✓ Created helper views';

-- ============================================================================
-- 步骤 7: 验证迁移
-- ============================================================================

RAISE NOTICE 'Step 7: Validating migration...';

DO $$
DECLARE
    total_rules INTEGER;
    global_rules INTEGER;
    dept_rules INTEGER;
    published_rules INTEGER;
    v_column_count INTEGER;
BEGIN
    -- 统计规则数
    SELECT COUNT(*) INTO total_rules FROM qc_rules;
    SELECT COUNT(*) INTO global_rules FROM qc_rules WHERE scope = 'global';
    SELECT COUNT(*) INTO dept_rules FROM qc_rules WHERE scope = 'department';
    SELECT COUNT(*) INTO published_rules FROM qc_rules WHERE status = 'published';

    -- 验证新增字段
    SELECT COUNT(*) INTO v_column_count
    FROM information_schema.columns
    WHERE table_name = 'qc_rules'
    AND column_name IN (
        'scope', 'department_id', 'parent_rule_id', 'override_action',
        'override_config', 'priority', 'status', 'effective_from',
        'effective_to', 'approved_by', 'approved_at'
    );

    IF v_column_count != 11 THEN
        RAISE EXCEPTION 'Missing columns in qc_rules table. Expected 11, found %', v_column_count;
    END IF;

    -- 验证审计日志表
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qc_rule_change_logs') THEN
        RAISE EXCEPTION 'qc_rule_change_logs table not created';
    END IF;

    -- 验证 RPC 函数
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'get_applicable_qc_rules'
    ) THEN
        RAISE EXCEPTION 'get_applicable_qc_rules function not created';
    END IF;

    -- 输出统计信息
    RAISE NOTICE '=== Migration Validation ===';
    RAISE NOTICE 'Total rules: %', total_rules;
    RAISE NOTICE 'Global rules: %', global_rules;
    RAISE NOTICE 'Department rules: %', dept_rules;
    RAISE NOTICE 'Published rules: %', published_rules;
    RAISE NOTICE 'New columns added: %', v_column_count;
    RAISE NOTICE '✓ All validations passed';
    RAISE NOTICE '============================';
END $$;

-- ============================================================================
-- 步骤 8: 示例数据（可选）
-- ============================================================================

-- 插入示例科室规则（注释掉，生产环境不需要）
/*
-- 示例1: 外科覆盖全局规则
INSERT INTO qc_rules (
    rule_code, name, description, category, rule_type, severity,
    scope, department_id, parent_rule_id, override_action, priority,
    status, check_logic, scoring_config
) VALUES (
    'COMP_001', '基本信息完整性-外科定制', '外科科室的基本信息完整性检查（覆盖全局规则）',
    'completeness', 'objective', 'critical',
    'department',
    (SELECT id FROM departments WHERE code = 'DEPT_002'),
    (SELECT id FROM qc_rules WHERE rule_code = 'COMP_001' AND scope = 'global'),
    'override', 10,
    'published', '{}', '{"default_deduction": 10, "max_deduction": 20}'
);

-- 示例2: 儿科禁用成人用药规则
INSERT INTO qc_rules (
    rule_code, name, description, category, rule_type, severity,
    scope, department_id, override_action, priority, status
) VALUES (
    'RATI_003', '禁用：成人药物剂量合理性', '儿科使用儿童用药剂量标准，禁用成人标准',
    'rationality', 'hybrid', 'major',
    'department',
    (SELECT id FROM departments WHERE code = 'DEPT_003'),
    'disable', 0, 'published'
);

-- 示例3: 骨科特有规则
INSERT INTO qc_rules (
    rule_code, name, description, category, rule_type, severity,
    scope, department_id, override_action, priority, status,
    check_logic, scoring_config
) VALUES (
    'DEPT_BONE_001', '手术部位标记检查', '骨科手术部位标记完整性检查',
    'completeness', 'objective', 'critical',
    'department',
    (SELECT id FROM departments WHERE code = 'DEPT_006'),
    'override', 20, 'published',
    '{}', '{"default_deduction": 15, "max_deduction": 30}'
);
*/

-- ============================================================================
-- 完成
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '╔════════════════════════════════════════════════════════════╗';
    RAISE NOTICE '║  ✅ Migration 009 Completed Successfully!                 ║';
    RAISE NOTICE '╠════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Changes:                                                  ║';
    RAISE NOTICE '║  • Extended qc_rules table with 11 new columns             ║';
    RAISE NOTICE '║  • Created qc_rule_change_logs audit table                 ║';
    RAISE NOTICE '║  • Created get_applicable_qc_rules RPC function            ║';
    RAISE NOTICE '║  • Created trigger for automatic audit logging             ║';
    RAISE NOTICE '║  • Created helper views for statistics                     ║';
    RAISE NOTICE '║  • Added 6 indexes for query optimization                  ║';
    RAISE NOTICE '╠════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Next Steps:                                               ║';
    RAISE NOTICE '║  1. Update backend API models and schemas                  ║';
    RAISE NOTICE '║  2. Implement department rule CRUD endpoints               ║';
    RAISE NOTICE '║  3. Update frontend UI for rule management                 ║';
    RAISE NOTICE '║  4. Run integration tests                                  ║';
    RAISE NOTICE '╚════════════════════════════════════════════════════════════╝';
    RAISE NOTICE '';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

