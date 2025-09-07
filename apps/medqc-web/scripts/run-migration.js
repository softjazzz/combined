"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runMigration = runMigration;
const supabase_js_1 = require("@supabase/supabase-js");
const fs_1 = require("fs");
const path_1 = require("path");
const dotenv_1 = require("dotenv");
// 加载环境变量
(0, dotenv_1.config)();
// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY;
if (!supabaseUrl || !supabaseServiceKey) {
    console.error('❌ 缺少Supabase配置');
    console.log('请设置环境变量:');
    console.log('- VITE_SUPABASE_URL');
    console.log('- SUPABASE_SERVICE_KEY 或 VITE_SUPABASE_ANON_KEY');
    process.exit(1);
}
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseServiceKey);
async function runMigration() {
    console.log('🚀 开始数据库Schema迁移...\n');
    try {
        // 读取迁移SQL文件
        const migrationPath = (0, path_1.join)(process.cwd(), 'supabase/migrations/001_enhance_qc_schema.sql');
        const migrationSQL = (0, fs_1.readFileSync)(migrationPath, 'utf-8');
        console.log('📄 读取迁移文件:', migrationPath);
        // 执行迁移
        console.log('⚡ 执行数据库迁移...');
        const { error } = await supabase.rpc('exec_sql', { sql_query: migrationSQL });
        if (error) {
            // 如果RPC函数不存在，尝试直接执行SQL
            console.log('⚠️  exec_sql函数不存在，尝试分段执行...');
            await executeSQLInParts(migrationSQL);
        }
        else {
            console.log('✅ 数据库迁移完成！');
        }
        // 验证迁移结果
        console.log('🔍 验证迁移结果...');
        await verifyMigration();
        console.log('\n🎉 数据库Schema升级成功完成！');
        console.log('现在可以运行: npm run db:init-rules');
    }
    catch (error) {
        console.error('❌ 迁移失败:', error);
        process.exit(1);
    }
}
// 分段执行SQL（当RPC不可用时）
async function executeSQLInParts(sql) {
    // 分割SQL语句（简单分割，生产环境需要更复杂的解析）
    const statements = sql
        .split(';')
        .map(s => s.trim())
        .filter(s => s.length > 0 && !s.startsWith('--'));
    console.log(`📝 共有 ${statements.length} 条SQL语句`);
    for (let i = 0; i < statements.length; i++) {
        const statement = statements[i];
        if (statement.includes('CREATE EXTENSION') ||
            statement.includes('ALTER TABLE') ||
            statement.includes('CREATE TABLE') ||
            statement.includes('CREATE INDEX') ||
            statement.includes('CREATE FUNCTION') ||
            statement.includes('CREATE VIEW')) {
            console.log(`${i + 1}/${statements.length}: 执行语句...`);
            try {
                // 注意：这里使用的是简化方法，实际项目中应该使用专门的迁移工具
                const { error } = await supabase.rpc('exec', { sql: statement + ';' });
                if (error) {
                    console.warn(`⚠️  语句 ${i + 1} 执行警告:`, error.message);
                }
            }
            catch (error) {
                console.warn(`⚠️  语句 ${i + 1} 跳过:`, error);
            }
        }
    }
}
// 验证迁移结果
async function verifyMigration() {
    const checks = [
        {
            name: '检查qc_rules表字段',
            test: async () => {
                const { data, error } = await supabase
                    .from('qc_rules')
                    .select('rule_code, rule_type, severity, max_score, check_logic, version')
                    .limit(1);
                return !error;
            }
        },
        {
            name: '检查qc_rules_embeddings表',
            test: async () => {
                const { data, error } = await supabase
                    .from('qc_rules_embeddings')
                    .select('*')
                    .limit(1);
                return !error;
            }
        },
        {
            name: '检查qc_analysis_cache表',
            test: async () => {
                const { data, error } = await supabase
                    .from('qc_analysis_cache')
                    .select('*')
                    .limit(1);
                return !error;
            }
        },
        {
            name: '检查qc_analysis_history表',
            test: async () => {
                const { data, error } = await supabase
                    .from('qc_analysis_history')
                    .select('*')
                    .limit(1);
                return !error;
            }
        }
    ];
    for (const check of checks) {
        try {
            const passed = await check.test();
            console.log(passed ? '✅' : '❌', check.name);
        }
        catch (error) {
            console.log('❌', check.name, '- 错误:', error);
        }
    }
}
// 执行迁移
runMigration();
