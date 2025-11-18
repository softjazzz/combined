-- 009_department_qc_rules_rollback.sql
-- 回滚 Migration 009: 科室级质控规则配置功能
--
-- 警告：此脚本将删除所有科室规则相关的数据和结构
-- 执行前请确保已备份数据
--
-- 版本: 2.0
-- 创建日期: 2025-10-12

-- ============================================================================
-- 步骤 0: 预检查
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== Starting Rollback of Migration 009 ===';
    RAISE NOTICE 'Timestamp: %', NOW();
    RAISE WARNING 'This will remove all department-level QC rules and related data!';
END $$;

-- ============================================================================
-- 步骤 1: 删除视图
-- ============================================================================

RAISE NOTICE 'Step 1: Dropping views...';

DROP VIEW IF EXISTS qc_rules_by_department CASCADE;
DROP VIEW IF EXISTS qc_rules_department_statistics CASCADE;

RAISE NOTICE '✓ Dropped views';

-- ============================================================================
-- 步骤 2: 删除 RPC 函数
-- ============================================================================

RAISE NOTICE 'Step 2: Dropping RPC function...';

DROP FUNCTION IF EXISTS get_applicable_qc_rules(UUID, TEXT, TIMESTAMPTZ) CASCADE;

RAISE NOTICE '✓ Dropped get_applicable_qc_rules function';

-- ============================================================================
-- 步骤 3: 删除触发器和触发器函数
-- ============================================================================

RAISE NOTICE 'Step 3: Dropping triggers...';

DROP TRIGGER IF EXISTS trigger_log_qc_rule_changes ON qc_rules;
DROP FUNCTION IF EXISTS log_qc_rule_changes() CASCADE;

RAISE NOTICE '✓ Dropped triggers and trigger functions';

-- ============================================================================
-- 步骤 4: 删除审计日志表
-- ============================================================================

RAISE NOTICE 'Step 4: Dropping qc_rule_change_logs table...';

DROP TABLE IF EXISTS qc_rule_change_logs CASCADE;

RAISE NOTICE '✓ Dropped qc_rule_change_logs table';

-- ============================================================================
-- 步骤 5: 删除索引
-- ============================================================================

RAISE NOTICE 'Step 5: Dropping indexes...';

DROP INDEX IF EXISTS uk_dept_rule_code_published;
DROP INDEX IF EXISTS idx_qc_rules_scope;
DROP INDEX IF EXISTS idx_qc_rules_department;
DROP INDEX IF EXISTS idx_qc_rules_parent;
DROP INDEX IF EXISTS idx_qc_rules_status;
DROP INDEX IF EXISTS idx_qc_rules_effective;
DROP INDEX IF EXISTS idx_qc_rules_composite;

RAISE NOTICE '✓ Dropped indexes';

-- ============================================================================
-- 步骤 6: 删除约束
-- ============================================================================

RAISE NOTICE 'Step 6: Dropping constraints...';

ALTER TABLE qc_rules DROP CONSTRAINT IF EXISTS chk_department_scope;

RAISE NOTICE '✓ Dropped constraints';

-- ============================================================================
-- 步骤 7: 删除科室规则数据
-- ============================================================================

RAISE NOTICE 'Step 7: Deleting department rules...';

DO $$
DECLARE
    deleted_count INTEGER := 0;
BEGIN
    -- 删除所有科室规则
    DELETE FROM qc_rules WHERE scope = 'department';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RAISE NOTICE '✓ Deleted % department rules', deleted_count;
END $$;

-- ============================================================================
-- 步骤 8: 删除新增的列
-- ============================================================================

RAISE NOTICE 'Step 8: Dropping columns from qc_rules table...';

DO $$
BEGIN
    -- 删除审核信息字段
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'approved_at'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN approved_at;
        RAISE NOTICE '✓ Dropped approved_at column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'approved_by'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN approved_by;
        RAISE NOTICE '✓ Dropped approved_by column';
    END IF;
    
    -- 删除生效期字段
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'effective_to'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN effective_to;
        RAISE NOTICE '✓ Dropped effective_to column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'effective_from'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN effective_from;
        RAISE NOTICE '✓ Dropped effective_from column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'status'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN status;
        RAISE NOTICE '✓ Dropped status column';
    END IF;
    
    -- 删除覆盖配置字段
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'priority'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN priority;
        RAISE NOTICE '✓ Dropped priority column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'override_config'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN override_config;
        RAISE NOTICE '✓ Dropped override_config column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'override_action'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN override_action;
        RAISE NOTICE '✓ Dropped override_action column';
    END IF;
    
    -- 删除规则范围和科室字段
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'parent_rule_id'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN parent_rule_id;
        RAISE NOTICE '✓ Dropped parent_rule_id column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'department_id'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN department_id;
        RAISE NOTICE '✓ Dropped department_id column';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' AND column_name = 'scope'
    ) THEN
        ALTER TABLE qc_rules DROP COLUMN scope;
        RAISE NOTICE '✓ Dropped scope column';
    END IF;
END $$;

-- ============================================================================
-- 步骤 9: 验证回滚
-- ============================================================================

RAISE NOTICE 'Step 9: Validating rollback...';

DO $$
DECLARE
    v_column_count INTEGER;
    v_table_exists BOOLEAN;
    v_function_exists BOOLEAN;
BEGIN
    -- 验证列已删除
    SELECT COUNT(*) INTO v_column_count
    FROM information_schema.columns
    WHERE table_name = 'qc_rules'
    AND column_name IN (
        'scope', 'department_id', 'parent_rule_id', 'override_action',
        'override_config', 'priority', 'status', 'effective_from',
        'effective_to', 'approved_by', 'approved_at'
    );
    
    IF v_column_count > 0 THEN
        RAISE WARNING 'Some columns were not dropped. Remaining: %', v_column_count;
    ELSE
        RAISE NOTICE '✓ All new columns removed';
    END IF;
    
    -- 验证审计日志表已删除
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'qc_rule_change_logs'
    ) INTO v_table_exists;
    
    IF v_table_exists THEN
        RAISE WARNING 'qc_rule_change_logs table still exists';
    ELSE
        RAISE NOTICE '✓ qc_rule_change_logs table removed';
    END IF;
    
    -- 验证 RPC 函数已删除
    SELECT EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'get_applicable_qc_rules'
    ) INTO v_function_exists;
    
    IF v_function_exists THEN
        RAISE WARNING 'get_applicable_qc_rules function still exists';
    ELSE
        RAISE NOTICE '✓ get_applicable_qc_rules function removed';
    END IF;
    
    RAISE NOTICE '=== Rollback Validation ===';
    RAISE NOTICE 'Columns remaining: %', v_column_count;
    RAISE NOTICE '============================';
END $$;

-- ============================================================================
-- 完成
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '╔════════════════════════════════════════════════════════════╗';
    RAISE NOTICE '║  ✅ Rollback of Migration 009 Completed!                  ║';
    RAISE NOTICE '╠════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Removed:                                                  ║';
    RAISE NOTICE '║  • 11 columns from qc_rules table                          ║';
    RAISE NOTICE '║  • qc_rule_change_logs audit table                         ║';
    RAISE NOTICE '║  • get_applicable_qc_rules RPC function                    ║';
    RAISE NOTICE '║  • Trigger for automatic audit logging                     ║';
    RAISE NOTICE '║  • Helper views for statistics                             ║';
    RAISE NOTICE '║  • All department rules data                               ║';
    RAISE NOTICE '╠════════════════════════════════════════════════════════════╣';
    RAISE NOTICE '║  Note:                                                     ║';
    RAISE NOTICE '║  The departments table was NOT removed (may be used        ║';
    RAISE NOTICE '║  by other features). Remove manually if needed.            ║';
    RAISE NOTICE '╚════════════════════════════════════════════════════════════╝';
    RAISE NOTICE '';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

