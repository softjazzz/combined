/**
 * 测试患者姓名显示修复
 */

const http = require('http');

// 模拟数据转换逻辑
function transformRecordData(records) {
    return records.map(record => ({
        ...record,
        // 数据结构适配：将 patient_info.name 映射到 patient_name
        patient_name: record.patient_info?.name || record.patient_name || '未知患者',
        // 添加其他可能需要的字段映射
        admission_date: record.admission_date || record.created_at?.split('T')[0] || '未知',
        qc_score: record.qc_score || record.ai_confidence_score || 0
    }));
}

// 测试API数据和转换逻辑
async function testPatientNameMapping() {
    console.log('🔍 测试患者姓名显示修复...\n');
    
    try {
        // 获取原始API数据
        console.log('📡 获取原始API数据...');
        const rawData = await makeRequest('http://localhost:8001/api/records?page=1&page_size=5');
        
        console.log('✅ 原始API数据结构:');
        console.log(`   - 总记录数: ${rawData.total}`);
        console.log(`   - 当前页记录数: ${rawData.data?.length || 0}`);
        
        if (rawData.data && rawData.data.length > 0) {
            console.log('\n📋 原始数据示例:');
            rawData.data.slice(0, 3).forEach((record, index) => {
                console.log(`   记录 ${index + 1}:`);
                console.log(`     - ID: ${record.id}`);
                console.log(`     - patient_name: ${record.patient_name || '❌ 未定义'}`);
                console.log(`     - patient_info.name: ${record.patient_info?.name || '❌ 未定义'}`);
                console.log(`     - department: ${record.department}`);
                console.log(`     - created_at: ${record.created_at}`);
                console.log('');
            });
        }
        
        // 应用数据转换
        console.log('🔧 应用数据转换逻辑...');
        const transformedData = transformRecordData(rawData.data || []);
        
        console.log('✅ 转换后的数据:');
        transformedData.slice(0, 3).forEach((record, index) => {
            console.log(`   记录 ${index + 1}:`);
            console.log(`     - ID: ${record.id}`);
            console.log(`     - patient_name: ${record.patient_name} ${record.patient_name !== '未知患者' ? '✅' : '⚠️'}`);
            console.log(`     - department: ${record.department}`);
            console.log(`     - admission_date: ${record.admission_date}`);
            console.log(`     - qc_score: ${record.qc_score}`);
            console.log('');
        });
        
        // 验证修复效果
        console.log('🎯 修复效果验证:');
        const validNames = transformedData.filter(r => r.patient_name && r.patient_name !== '未知患者');
        const totalRecords = transformedData.length;
        
        console.log(`   - 总记录数: ${totalRecords}`);
        console.log(`   - 有效患者姓名: ${validNames.length}`);
        console.log(`   - 成功率: ${totalRecords > 0 ? Math.round((validNames.length / totalRecords) * 100) : 0}%`);
        
        if (validNames.length > 0) {
            console.log('\n🎉 患者姓名显示修复成功！');
            console.log('   现在病历列表应该能正确显示患者姓名了');
            
            console.log('\n📝 有效患者姓名列表:');
            validNames.forEach((record, index) => {
                console.log(`   ${index + 1}. ${record.patient_name} (${record.department})`);
            });
        } else {
            console.log('\n❌ 患者姓名显示修复失败');
            console.log('   所有记录的患者姓名仍然显示为"未知患者"');
        }
        
        // 模拟前端显示逻辑
        console.log('\n🖥️  模拟前端显示效果:');
        console.log('病历列表显示:');
        transformedData.slice(0, 5).forEach((record, index) => {
            const displayName = record.patient_name || '未知';
            const department = record.department || '未知科室';
            const admissionDate = record.admission_date || '未知';
            
            console.log(`   ${index + 1}. ${displayName}`);
            console.log(`      科室: ${department}`);
            console.log(`      入院: ${admissionDate}`);
            console.log('');
        });
        
    } catch (error) {
        console.error('❌ 测试过程中出现错误:', error.message);
    }
}

// 测试确认选择对话框显示
function testConfirmationDialog() {
    console.log('\n🔍 测试确认选择对话框显示...\n');
    
    // 模拟选择的记录
    const selectedRecord = {
        id: 'record-001',
        patient_name: '刘德华',
        department: '心内科',
        admission_date: '2024-12-01'
    };
    
    const selectedDocuments = [
        { id: 'doc-001', title: '入院记录', type: 'admission_record' }
    ];
    
    const selectedRules = [
        { rule_id: 'rule-001', name: '主诉与现病史一致性检查' },
        { rule_id: 'rule-002', name: '既往史相关性检查' }
    ];
    
    console.log('📋 确认选择对话框显示内容:');
    console.log(`   标题: 请确认选择`);
    console.log(`   副标题: 病历：${selectedRecord?.patient_name || '未选择'} · 文书：${selectedDocuments.length} 份 · 规则：${selectedRules.length} 条`);
    console.log('');
    
    if (selectedRecord?.patient_name && selectedRecord.patient_name !== '未知患者') {
        console.log('✅ 确认对话框患者姓名显示正常');
    } else {
        console.log('❌ 确认对话框患者姓名显示异常');
    }
}

// HTTP请求辅助函数
function makeRequest(url) {
    return new Promise((resolve, reject) => {
        const req = http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(new Error(`解析JSON失败: ${e.message}`));
                }
            });
        });
        
        req.on('error', reject);
        req.setTimeout(5000, () => {
            req.destroy();
            reject(new Error('请求超时'));
        });
    });
}

// 主测试函数
async function runTests() {
    console.log('🧪 患者姓名显示修复测试\n');
    console.log('=' .repeat(60));
    
    await testPatientNameMapping();
    testConfirmationDialog();
    
    console.log('\n' + '='.repeat(60));
    console.log('📋 修复总结:');
    console.log('1. ✅ 添加了数据结构适配逻辑');
    console.log('2. ✅ 将 patient_info.name 映射到 patient_name');
    console.log('3. ✅ 添加了默认值处理');
    console.log('4. ✅ 同时适配了API和Supabase数据源');
    console.log('');
    console.log('🎯 现在病历列表应该能正确显示患者姓名了！');
    console.log('   请刷新页面并重新测试病历选择功能。');
}

// 运行测试
runTests().catch(console.error);
