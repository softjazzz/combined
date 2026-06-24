#!/usr/bin/env node
"use strict";
/**
 * 运行AI增强功能数据库迁移
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const url_1 = require("url");
const __filename = (0, url_1.fileURLToPath)(import.meta.url);
const __dirname = path_1.default.dirname(__filename);
// Supabase配置
const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseServiceKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MjA0MTg3NCwiZXhwIjoyMDY3NjE3ODc0fQ.Nj6OVJx1-wvYKGJVhKXONQKQGsWFGcBjMhyOA4UKUyU';
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseServiceKey);
async function runMigration() {
    try {
        console.log('🚀 开始运行AI增强功能数据库迁移...');
        // 读取迁移文件
        const migrationPath = path_1.default.join(__dirname, '../supabase/migrations/003_add_ai_enhancement_support.sql');
        const migrationSQL = fs_1.default.readFileSync(migrationPath, 'utf8');
        // 按分号分割SQL语句
        const statements = migrationSQL
            .split(';')
            .map(stmt => stmt.trim())
            .filter(stmt => stmt.length > 0 && !stmt.startsWith('--'));
        console.log(`📝 共有 ${statements.length} 条SQL语句`);
        // 逐条执行SQL语句
        for (let i = 0; i < statements.length; i++) {
            const statement = statements[i];
            if (statement.length === 0)
                continue;
            console.log(`${i + 1}/${statements.length}: 执行语句...`);
            try {
                const { error } = await supabase.rpc('exec_sql', { sql: statement });
                if (error) {
                    console.log(`⚠️  语句 ${i + 1} 执行警告:`, error.message);
                    // 继续执行其他语句
                }
                else {
                    console.log(`✅ 语句 ${i + 1} 执行成功`);
                }
            }
            catch (err) {
                console.log(`⚠️  语句 ${i + 1} 执行异常:`, err);
                // 继续执行其他语句
            }
        }
        console.log('🔍 验证迁移结果...');
        // 验证新表是否创建成功
        const tables = [
            'ai_learning_records',
            'ai_knowledge_base',
            'ai_performance_metrics',
            'ai_learning_tasks',
            'ai_model_versions',
            'multimodal_analysis_results',
            'context_analysis_cache',
            'patient_history_analysis'
        ];
        for (const table of tables) {
            const { data, error } = await supabase
                .from(table)
                .select('*')
                .limit(1);
            if (error) {
                console.log(`❌ 检查表 ${table} 失败:`, error.message);
            }
            else {
                console.log(`✅ 检查表 ${table} 成功`);
            }
        }
        // 验证视图是否创建成功
        const views = [
            'ai_performance_summary',
            'learning_progress_summary',
            'knowledge_base_summary',
            'learning_tasks_summary'
        ];
        for (const view of views) {
            try {
                const { data, error } = await supabase
                    .from(view)
                    .select('*')
                    .limit(1);
                if (error) {
                    console.log(`❌ 检查视图 ${view} 失败:`, error.message);
                }
                else {
                    console.log(`✅ 检查视图 ${view} 成功`);
                }
            }
            catch (err) {
                console.log(`❌ 检查视图 ${view} 异常:`, err);
            }
        }
        // 验证函数是否创建成功
        try {
            const { data, error } = await supabase.rpc('calculate_ai_analysis_quality', {
                p_record_id: '00000000-0000-0000-0000-000000000000',
                p_time_window_hours: 24
            });
            if (error) {
                console.log(`❌ 检查函数 calculate_ai_analysis_quality 失败:`, error.message);
            }
            else {
                console.log(`✅ 检查函数 calculate_ai_analysis_quality 成功`);
            }
        }
        catch (err) {
            console.log(`❌ 检查函数异常:`, err);
        }
        console.log('🎉 AI增强功能数据库迁移完成！');
        console.log('💡 现在可以使用以下新功能：');
        console.log('   - 智能学习和反馈系统');
        console.log('   - 知识库管理');
        console.log('   - 性能监控和优化');
        console.log('   - 多模态分析');
        console.log('   - 上下文感知分析');
    }
    catch (error) {
        console.error('❌ 迁移失败:', error);
        process.exit(1);
    }
}
// 运行迁移
if (import.meta.url === `file://${process.argv[1]}`) {
    runMigration();
}
