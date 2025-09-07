#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseKey);
async function checkTableColumns() {
    try {
        console.log('🔍 检查medical_records表列结构...\n');
        // 尝试插入一个最小的记录来看哪些字段是必需的
        const minimalRecord = {
            patient_name: 'test',
            content: 'test content'
        };
        console.log('📝 尝试插入最小记录...');
        const { data: minimalResult, error: minimalError } = await supabase
            .from('medical_records')
            .insert(minimalRecord)
            .select()
            .single();
        if (minimalError) {
            console.log('❌ 最小记录插入失败:', minimalError.message);
        }
        else {
            console.log('✅ 最小记录插入成功:', minimalResult.id);
            // 清理测试数据
            await supabase
                .from('medical_records')
                .delete()
                .eq('id', minimalResult.id);
            console.log('🧹 清理测试数据完成');
        }
        // 尝试插入包含admission_date的记录
        console.log('\n📝 尝试插入包含admission_date的记录...');
        const recordWithDate = {
            patient_name: 'test patient',
            content: 'test content',
            admission_date: '2024-01-15'
        };
        const { data: dateResult, error: dateError } = await supabase
            .from('medical_records')
            .insert(recordWithDate)
            .select()
            .single();
        if (dateError) {
            console.log('❌ 包含admission_date的记录插入失败:', dateError.message);
            // 尝试不同的日期格式
            console.log('\n📝 尝试不同的日期格式...');
            const recordWithISODate = {
                patient_name: 'test patient',
                content: 'test content',
                admission_date: new Date('2024-01-15').toISOString()
            };
            const { data: isoResult, error: isoError } = await supabase
                .from('medical_records')
                .insert(recordWithISODate)
                .select()
                .single();
            if (isoError) {
                console.log('❌ ISO日期格式也失败:', isoError.message);
            }
            else {
                console.log('✅ ISO日期格式成功:', isoResult.id);
                // 清理
                await supabase.from('medical_records').delete().eq('id', isoResult.id);
            }
        }
        else {
            console.log('✅ 包含admission_date的记录插入成功:', dateResult.id);
            // 清理
            await supabase.from('medical_records').delete().eq('id', dateResult.id);
        }
        // 查询现有记录的结构
        console.log('\n📋 查询现有记录结构...');
        const { data: existingRecords, error: queryError } = await supabase
            .from('medical_records')
            .select('*')
            .limit(1);
        if (queryError) {
            console.log('❌ 查询失败:', queryError.message);
        }
        else if (existingRecords && existingRecords.length > 0) {
            console.log('✅ 现有记录字段:', Object.keys(existingRecords[0]));
        }
        else {
            console.log('💡 表为空，没有现有记录');
        }
    }
    catch (error) {
        console.error('❌ 检查失败:', error);
    }
}
checkTableColumns()
    .then(() => {
    console.log('\n🎉 列结构检查完成');
    process.exit(0);
})
    .catch(error => {
    console.error('❌ 检查过程异常:', error);
    process.exit(1);
});
