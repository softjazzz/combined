"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.initBaseSchema = initBaseSchema;
const supabase_js_1 = require("@supabase/supabase-js");
const fs_1 = require("fs");
const path_1 = require("path");
const dotenv_1 = require("dotenv");
// 加载环境变量
(0, dotenv_1.config)();
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseServiceKey = process.env.VITE_SUPABASE_ANON_KEY;
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseServiceKey);
async function initBaseSchema() {
    console.log('🚀 初始化基础数据库Schema...\n');
    try {
        // 读取基础schema文件
        const schemaPath = (0, path_1.join)(process.cwd(), 'supabase/migrations/000_init_base_schema.sql');
        const schemaSQL = (0, fs_1.readFileSync)(schemaPath, 'utf-8');
        console.log('📄 读取基础schema文件:', schemaPath);
        console.log('📝 即将在Supabase Dashboard中执行SQL');
        console.log('⚠️  请手动在Supabase Dashboard -> SQL Editor 中执行以下SQL:\n');
        console.log('='.repeat(80));
        console.log(schemaSQL);
        console.log('='.repeat(80));
        console.log('\n📋 执行步骤:');
        console.log('1. 打开 https://app.supabase.com/project/afsbjvihjfsngobccnjx/sql');
        console.log('2. 复制上面的SQL代码');
        console.log('3. 粘贴到SQL Editor中');
        console.log('4. 点击"Run"按钮执行');
        console.log('5. 执行完成后，运行: pnpm run verify-schema');
    }
    catch (error) {
        console.error('❌ 读取schema文件失败:', error);
        process.exit(1);
    }
}
// 执行初始化
initBaseSchema();
