"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg';
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseAnonKey);
async function verifyPatientData() {
    console.log('🔍 验证患者数据...\n');
    try {
        // 1. 查询所有病案记录
        const { data: records, error, count } = await supabase
            .from('medical_records')
            .select('*', { count: 'exact' })
            .order('created_at', { ascending: false });
        if (error) {
            throw error;
        }
        console.log(`📊 数据库统计:`);
        console.log(`- 总记录数: ${count}`);
        console.log(`- 返回记录数: ${records?.length || 0}\n`);
        if (records && records.length > 0) {
            console.log('📋 患者列表:');
            records.forEach((record, index) => {
                console.log(`${index + 1}. ${record.patient_name} (${record.patient_age}岁, ${record.patient_gender === 'M' ? '男' : '女'}) - ${record.department}`);
                console.log(`   状态: ${record.status}`);
                console.log(`   创建时间: ${record.created_at}`);
                console.log(`   病历长度: ${record.content?.length || 0} 字符`);
                console.log('');
            });
            // 2. 统计科室分布
            const departmentStats = {};
            records.forEach(record => {
                departmentStats[record.department] = (departmentStats[record.department] || 0) + 1;
            });
            console.log('🏥 科室分布:');
            Object.entries(departmentStats).forEach(([dept, count]) => {
                console.log(`- ${dept}: ${count} 条`);
            });
            // 3. 统计状态分布
            const statusStats = {};
            records.forEach(record => {
                statusStats[record.status] = (statusStats[record.status] || 0) + 1;
            });
            console.log('\n📈 状态分布:');
            Object.entries(statusStats).forEach(([status, count]) => {
                console.log(`- ${status}: ${count} 条`);
            });
            // 4. 检查病历内容长度
            const contentLengths = records.map(r => r.content?.length || 0);
            const avgLength = contentLengths.reduce((a, b) => a + b, 0) / contentLengths.length;
            const minLength = Math.min(...contentLengths);
            const maxLength = Math.max(...contentLengths);
            console.log('\n📝 病历内容统计:');
            console.log(`- 平均长度: ${Math.round(avgLength)} 字符`);
            console.log(`- 最短长度: ${minLength} 字符`);
            console.log(`- 最长长度: ${maxLength} 字符`);
        }
        else {
            console.log('❌ 数据库中没有找到任何病案记录');
            console.log('请运行 create-extended-patients-only.ts 脚本创建测试数据');
        }
    }
    catch (error) {
        console.error('❌ 验证失败:', error);
    }
}
// 运行验证
verifyPatientData().catch(console.error);
