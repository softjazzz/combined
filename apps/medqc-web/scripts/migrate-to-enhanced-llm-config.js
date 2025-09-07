#!/usr/bin/env tsx
"use strict";
/**
 * 数据库迁移脚本：升级到增强的LLM配置支持
 *
 * 此脚本将：
 * 1. 创建新的LLM配置相关表
 * 2. 更新现有表结构以支持多模型配置
 * 3. 插入预配置的LLM提供商和模型数据
 * 4. 保持向后兼容性
 */
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const fs_1 = require("fs");
const path_1 = require("path");
const dotenv_1 = require("dotenv");
// 加载环境变量
(0, dotenv_1.config)();
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.VITE_SUPABASE_ANON_KEY;
if (!supabaseUrl || !supabaseServiceKey) {
    console.error('❌ 缺少必要的环境变量:');
    console.error('   VITE_SUPABASE_URL:', supabaseUrl ? '✓' : '❌');
    console.error('   SUPABASE_SERVICE_ROLE_KEY:', supabaseServiceKey ? '✓' : '❌');
    process.exit(1);
}
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseServiceKey);
async function runEnhancedLLMConfigMigration() {
    console.log('🚀 开始增强LLM配置迁移...\n');
    try {
        // 1. 检查当前数据库状态
        console.log('📋 检查当前数据库状态...');
        await checkCurrentState();
        // 2. 创建新的LLM配置表
        console.log('\n🔧 创建LLM配置表...');
        await createLLMConfigTables();
        // 3. 更新现有表结构
        console.log('\n📝 更新现有表结构...');
        await updateExistingTables();
        // 4. 插入预配置数据
        console.log('\n📊 插入LLM提供商和模型配置...');
        await insertLLMConfigData();
        // 5. 创建索引和触发器
        console.log('\n⚡ 创建索引和触发器...');
        await createIndexesAndTriggers();
        // 6. 创建便捷查询函数
        console.log('\n🔍 创建便捷查询函数...');
        await createUtilityFunctions();
        // 7. 验证迁移结果
        console.log('\n✅ 验证迁移结果...');
        await verifyMigration();
        console.log('\n🎉 增强LLM配置迁移完成！');
        console.log('现在支持：');
        console.log('  ✓ 多厂商LLM API配置');
        console.log('  ✓ 每个厂商的多模型选择');
        console.log('  ✓ 统一的端点配置');
        console.log('  ✓ 用户个性化配置');
        console.log('  ✓ 详细的使用统计');
    }
    catch (error) {
        console.error('❌ 迁移失败:', error);
        process.exit(1);
    }
}
async function checkCurrentState() {
    // 检查是否已经存在LLM配置表
    const { error: providersError } = await supabase
        .from('llm_api_providers')
        .select('*')
        .limit(1);
    if (!providersError) {
        console.log('⚠️  LLM配置表已存在，将跳过创建步骤');
        return;
    }
    console.log('✓ 准备创建新的LLM配置表');
}
async function createLLMConfigTables() {
    const createTablesSQL = `
    -- 创建LLM API提供商表
    CREATE TABLE IF NOT EXISTS llm_api_providers (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        provider_code VARCHAR(50) UNIQUE NOT NULL,
        provider_name VARCHAR(100) NOT NULL,
        base_endpoint VARCHAR(500) NOT NULL,
        request_format VARCHAR(20) NOT NULL DEFAULT 'openai',
        requires_api_key BOOLEAN DEFAULT TRUE,
        description TEXT,
        features JSONB DEFAULT '[]',
        is_active BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- 创建LLM模型配置表
    CREATE TABLE IF NOT EXISTS llm_models (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        provider_id UUID REFERENCES llm_api_providers(id) ON DELETE CASCADE,
        model_code VARCHAR(100) NOT NULL,
        model_name VARCHAR(100) NOT NULL,
        description TEXT,
        context_length INTEGER,
        pricing_tier VARCHAR(20),
        capabilities JSONB DEFAULT '[]',
        parameters JSONB DEFAULT '{}',
        is_default BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT unique_default_per_provider UNIQUE (provider_id, is_default) DEFERRABLE INITIALLY DEFERRED
    );

    -- 创建用户LLM配置表
    CREATE TABLE IF NOT EXISTS user_llm_configs (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID,
        config_name VARCHAR(100) NOT NULL,
        provider_id UUID REFERENCES llm_api_providers(id),
        model_id UUID REFERENCES llm_models(id),
        api_key_encrypted TEXT,
        custom_endpoint VARCHAR(500),
        custom_parameters JSONB DEFAULT '{}',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT unique_user_config UNIQUE (user_id, config_name)
    );
  `;
    const { error } = await supabase.rpc('exec_sql', { sql_query: createTablesSQL });
    if (error) {
        // 如果RPC不存在，尝试分段执行
        console.log('使用分段执行方式...');
        await executeSQLInParts(createTablesSQL);
    }
    console.log('✓ LLM配置表创建完成');
}
async function updateExistingTables() {
    const updateSQL = `
    -- 为medical_records表添加AI模型信息字段
    ALTER TABLE medical_records 
    ADD COLUMN IF NOT EXISTS ai_model_used VARCHAR(100),
    ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(50);

    -- 为ai_parsing_history表添加模型关联字段
    ALTER TABLE ai_parsing_history 
    ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES llm_api_providers(id),
    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES llm_models(id);
  `;
    const { error } = await supabase.rpc('exec_sql', { sql_query: updateSQL });
    if (error) {
        await executeSQLInParts(updateSQL);
    }
    console.log('✓ 现有表结构更新完成');
}
async function insertLLMConfigData() {
    // 读取完整的配置数据SQL
    const configDataPath = (0, path_1.join)(process.cwd(), 'supabase/setup-database.sql');
    const fullSQL = (0, fs_1.readFileSync)(configDataPath, 'utf-8');
    // 提取LLM配置数据部分
    const configDataSQL = extractLLMConfigData(fullSQL);
    const { error } = await supabase.rpc('exec_sql', { sql_query: configDataSQL });
    if (error) {
        await executeSQLInParts(configDataSQL);
    }
    console.log('✓ LLM配置数据插入完成');
}
async function createIndexesAndTriggers() {
    const indexesSQL = `
    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_llm_providers_code ON llm_api_providers(provider_code);
    CREATE INDEX IF NOT EXISTS idx_llm_providers_active ON llm_api_providers(is_active);
    CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models(provider_id);
    CREATE INDEX IF NOT EXISTS idx_llm_models_code ON llm_models(model_code);
    CREATE INDEX IF NOT EXISTS idx_llm_models_active ON llm_models(is_active);
    CREATE INDEX IF NOT EXISTS idx_llm_models_default ON llm_models(is_default);
    CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user ON user_llm_configs(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_llm_configs_active ON user_llm_configs(is_active);
    CREATE INDEX IF NOT EXISTS idx_medical_records_ai_provider ON medical_records(ai_provider);
    CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_provider ON ai_parsing_history(provider_id);
    CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_model ON ai_parsing_history(model_id);

    -- 创建触发器
    CREATE TRIGGER update_llm_api_providers_updated_at 
        BEFORE UPDATE ON llm_api_providers 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

    CREATE TRIGGER update_llm_models_updated_at 
        BEFORE UPDATE ON llm_models 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

    CREATE TRIGGER update_user_llm_configs_updated_at 
        BEFORE UPDATE ON user_llm_configs 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  `;
    const { error } = await supabase.rpc('exec_sql', { sql_query: indexesSQL });
    if (error) {
        await executeSQLInParts(indexesSQL);
    }
    console.log('✓ 索引和触发器创建完成');
}
async function createUtilityFunctions() {
    const functionsSQL = `
    -- 获取提供商的所有模型
    CREATE OR REPLACE FUNCTION get_provider_models(provider_code_param VARCHAR)
    RETURNS TABLE (
        model_id UUID,
        model_code VARCHAR,
        model_name VARCHAR,
        description TEXT,
        context_length INTEGER,
        pricing_tier VARCHAR,
        capabilities JSONB,
        is_default BOOLEAN
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            m.id, m.model_code, m.model_name, m.description,
            m.context_length, m.pricing_tier, m.capabilities, m.is_default
        FROM llm_models m
        JOIN llm_api_providers p ON m.provider_id = p.id
        WHERE p.provider_code = provider_code_param AND m.is_active = TRUE
        ORDER BY m.sort_order;
    END;
    $$ LANGUAGE plpgsql;

    -- 创建LLM使用统计视图
    CREATE OR REPLACE VIEW llm_usage_stats AS
    SELECT 
        p.provider_name,
        m.model_name,
        COUNT(*) as usage_count,
        AVG(aph.processing_time_ms) as avg_processing_time,
        SUM(aph.tokens_used) as total_tokens_used,
        AVG((aph.confidence_scores->>'overall')::numeric) as avg_confidence
    FROM ai_parsing_history aph
    JOIN llm_api_providers p ON aph.provider_id = p.id
    JOIN llm_models m ON aph.model_id = m.id
    WHERE aph.created_at >= date_trunc('month', CURRENT_DATE)
    GROUP BY p.provider_name, m.model_name
    ORDER BY usage_count DESC;
  `;
    const { error } = await supabase.rpc('exec_sql', { sql_query: functionsSQL });
    if (error) {
        await executeSQLInParts(functionsSQL);
    }
    console.log('✓ 便捷查询函数创建完成');
}
async function verifyMigration() {
    // 验证表是否创建成功
    const tables = ['llm_api_providers', 'llm_models', 'user_llm_configs'];
    for (const table of tables) {
        const { data, error } = await supabase.from(table).select('*').limit(1);
        if (error) {
            throw new Error(`表 ${table} 验证失败: ${error.message}`);
        }
        console.log(`✓ 表 ${table} 验证通过`);
    }
    // 验证配置数据是否插入成功
    const { data: providers } = await supabase
        .from('llm_api_providers')
        .select('*');
    const { data: models } = await supabase
        .from('llm_models')
        .select('*');
    console.log(`✓ 已配置 ${providers?.length || 0} 个LLM提供商`);
    console.log(`✓ 已配置 ${models?.length || 0} 个模型`);
}
// 辅助函数：分段执行SQL
async function executeSQLInParts(sql) {
    const statements = sql.split(';').filter(s => s.trim());
    for (const statement of statements) {
        if (statement.trim()) {
            const { error } = await supabase.rpc('exec_sql', { sql_query: statement + ';' });
            if (error) {
                console.warn(`SQL执行警告: ${error.message}`);
            }
        }
    }
}
// 辅助函数：提取LLM配置数据
function extractLLMConfigData(fullSQL) {
    const startMarker = '-- 10. 插入LLM API提供商配置数据';
    const endMarker = '-- 12. 插入示例医疗记录数据';
    const startIndex = fullSQL.indexOf(startMarker);
    const endIndex = fullSQL.indexOf(endMarker);
    if (startIndex === -1 || endIndex === -1) {
        throw new Error('无法找到LLM配置数据部分');
    }
    return fullSQL.substring(startIndex, endIndex);
}
// 运行迁移
if (require.main === module) {
    runEnhancedLLMConfigMigration();
}
