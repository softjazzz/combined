#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseKey);
async function checkDatabaseSchema() {
    try {
        console.log('🔍 检查数据库Schema...');
        // 检查所有需要的表
        // 尝试查询medical_records表结构
        console.log('\n📋 检查medical_records表...');
        const { data, error } = await supabase
            .from('medical_records')
            .select('*')
            .limit(0);
        if (error) {
            console.error('❌ medical_records表错误:', error.message);
            // 如果表不存在，尝试创建
            if (error.message.includes('relation') && error.message.includes('does not exist')) {
                console.log('🔧 尝试创建medical_records表...');
                await createMedicalRecordsTable();
            }
        }
        else {
            console.log('✅ medical_records表存在');
        }
        // 检查其他表
        const requiredTables = ['qc_results', 'qc_rules', 'qc_analysis_cache', 'qc_analysis_history'];
        for (const table of requiredTables) {
            console.log(`\n📋 检查${table}表...`);
            const { error: tableError } = await supabase
                .from(table)
                .select('*')
                .limit(0);
            if (tableError) {
                console.error(`❌ ${table}表错误:`, tableError.message);
            }
            else {
                console.log(`✅ ${table}表存在`);
            }
        }
    }
    catch (error) {
        console.error('❌ Schema检查失败:', error);
    }
}
async function createMedicalRecordsTable() {
    try {
        const createTableSQL = `
      CREATE TABLE IF NOT EXISTS medical_records (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        patient_name TEXT NOT NULL,
        patient_id TEXT,
        department TEXT,
        doctor_name TEXT,
        admission_date DATE,
        discharge_date DATE,
        content TEXT NOT NULL,
        file_url TEXT,
        file_type TEXT,
        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'analyzing', 'completed', 'failed')),
        qc_score INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      
      -- 创建更新时间触发器
      CREATE OR REPLACE FUNCTION update_updated_at_column()
      RETURNS TRIGGER AS $$
      BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
      END;
      $$ language 'plpgsql';
      
      CREATE TRIGGER update_medical_records_updated_at 
        BEFORE UPDATE ON medical_records 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    `;
        const { error } = await supabase.rpc('exec_sql', { sql: createTableSQL });
        if (error) {
            console.error('❌ 创建表失败:', error);
        }
        else {
            console.log('✅ medical_records表创建成功');
        }
    }
    catch (error) {
        console.error('❌ 创建表异常:', error);
    }
}
checkDatabaseSchema()
    .then(() => {
    console.log('\n🎉 Schema检查完成');
    process.exit(0);
})
    .catch(error => {
    console.error('❌ 检查过程异常:', error);
    process.exit(1);
});
