#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
// 需要使用service role key进行管理操作，但我们先用anon key测试
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseKey);
async function setupDatabase() {
    console.log('🔧 开始设置数据库...\n');
    try {
        // 1. 创建medical_records表
        console.log('📋 创建medical_records表...');
        const createMedicalRecordsTable = `
      -- 删除现有表（如果存在）
      DROP TABLE IF EXISTS medical_records CASCADE;
      
      -- 创建medical_records表
      CREATE TABLE medical_records (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        patient_name TEXT NOT NULL,
        patient_age INTEGER,
        patient_gender TEXT CHECK (patient_gender IN ('M', 'F', 'U')),
        department TEXT,
        admission_date DATE,
        record_type TEXT CHECK (record_type IN ('inpatient', 'outpatient', 'emergency')),
        content TEXT NOT NULL,
        file_url TEXT,
        file_name TEXT,
        file_size INTEGER,
        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'analyzing', 'completed', 'failed')),
        qc_score INTEGER,
        qc_grade TEXT CHECK (qc_grade IN ('A', 'B', 'C')),
        hospital_id UUID,
        doctor_id UUID,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      
      -- 创建索引
      CREATE INDEX idx_medical_records_status ON medical_records(status);
      CREATE INDEX idx_medical_records_department ON medical_records(department);
      CREATE INDEX idx_medical_records_created_at ON medical_records(created_at);
      
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
        // 由于我们没有service role，尝试使用简单的方法
        console.log('⚠️  注意：使用anon key可能无法执行DDL操作');
        console.log('📝 SQL脚本已准备，需要在Supabase控制台中执行：');
        console.log(createMedicalRecordsTable);
        // 2. 尝试禁用RLS或创建允许的策略
        console.log('\n🔒 设置RLS策略...');
        const rlsPolicy = `
      -- 启用RLS
      ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
      
      -- 创建允许匿名用户操作的策略（仅用于开发环境）
      CREATE POLICY "Allow anonymous access for development" ON medical_records
        FOR ALL USING (true) WITH CHECK (true);
    `;
        console.log('📝 RLS策略脚本：');
        console.log(rlsPolicy);
        // 3. 创建其他表
        console.log('\n📋 创建其他表...');
        const createOtherTables = `
      -- 创建qc_results表
      CREATE TABLE IF NOT EXISTS qc_results (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        medical_record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
        overall_score INTEGER NOT NULL,
        completeness_score INTEGER,
        consistency_score INTEGER,
        rationality_score INTEGER,
        timeliness_score INTEGER,
        issues JSONB,
        suggestions JSONB,
        analysis_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      
      -- 创建qc_rules表
      CREATE TABLE IF NOT EXISTS qc_rules (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        weight DECIMAL(3,2) DEFAULT 1.0,
        is_active BOOLEAN DEFAULT true,
        prompt_template TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      
      -- 创建qc_analysis_cache表
      CREATE TABLE IF NOT EXISTS qc_analysis_cache (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        content_hash TEXT UNIQUE NOT NULL,
        analysis_result JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        expires_at TIMESTAMP WITH TIME ZONE
      );
      
      -- 创建qc_analysis_history表
      CREATE TABLE IF NOT EXISTS qc_analysis_history (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        medical_record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
        analysis_result JSONB NOT NULL,
        analysis_version TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
      
      -- 为所有表启用RLS并创建开发策略
      ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
      ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
      ALTER TABLE qc_analysis_cache ENABLE ROW LEVEL SECURITY;
      ALTER TABLE qc_analysis_history ENABLE ROW LEVEL SECURITY;
      
      CREATE POLICY "Allow anonymous access for development" ON qc_results
        FOR ALL USING (true) WITH CHECK (true);
      CREATE POLICY "Allow anonymous access for development" ON qc_rules
        FOR ALL USING (true) WITH CHECK (true);
      CREATE POLICY "Allow anonymous access for development" ON qc_analysis_cache
        FOR ALL USING (true) WITH CHECK (true);
      CREATE POLICY "Allow anonymous access for development" ON qc_analysis_history
        FOR ALL USING (true) WITH CHECK (true);
    `;
        console.log('📝 其他表创建脚本：');
        console.log(createOtherTables);
        console.log('\n💡 请在Supabase控制台的SQL编辑器中执行以上脚本');
        console.log('💡 或者提供service role key以自动执行');
    }
    catch (error) {
        console.error('❌ 设置失败:', error);
    }
}
setupDatabase()
    .then(() => {
    console.log('\n🎉 数据库设置脚本生成完成');
    process.exit(0);
})
    .catch(error => {
    console.error('❌ 设置过程异常:', error);
    process.exit(1);
});
