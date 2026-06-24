#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
console.log('🔧 Supabase连接测试');
console.log('URL:', supabaseUrl);
console.log('Key前缀:', supabaseKey?.substring(0, 20) + '...');
if (!supabaseUrl || !supabaseKey) {
    console.error('❌ 环境变量缺失');
    process.exit(1);
}
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseKey);
async function testConnection() {
    try {
        console.log('\n🧪 测试数据库连接...');
        // 测试简单查询
        const { data, error } = await supabase
            .from('medical_records')
            .select('count')
            .limit(1);
        if (error) {
            console.error('❌ 数据库查询失败:', error.message);
            return false;
        }
        console.log('✅ 数据库连接成功');
        return true;
    }
    catch (error) {
        console.error('❌ 连接测试失败:', error);
        return false;
    }
}
testConnection()
    .then(success => {
    process.exit(success ? 0 : 1);
})
    .catch(error => {
    console.error('❌ 测试过程异常:', error);
    process.exit(1);
});
