/**
 * 验证入院记录质控规则修复
 * 模拟前端组件的完整流程
 */

const https = require('https');
const http = require('http');

// 模拟前端的API调用
async function fetchQCRules() {
    return new Promise((resolve, reject) => {
        const req = http.get('http://localhost:8001/api/qc/sichuan/rules?grouped=true', (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(e);
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

// 修复后的规则获取函数（与前端代码一致）
function getApplicableRules(categoryCode, rulesByDocumentType) {
    return rulesByDocumentType[categoryCode] || [];
}

// 模拟文书类型配置
const documentCategories = [
    {
        category_code: 'admission_record',
        category_name: '入院记录',
        description: '患者入院时的基本信息和病情记录'
    },
    {
        category_code: 'progress_note',
        category_name: '病程记录',
        description: '患者住院期间的病情变化记录'
    },
    {
        category_code: 'discharge_record',
        category_name: '出院记录',
        description: '患者出院时的总结记录'
    }
];

async function verifyFix() {
    console.log('🔍 验证入院记录质控规则修复\n');
    
    try {
        // 1. 获取API数据
        console.log('📡 获取质控规则数据...');
        const apiData = await fetchQCRules();
        
        console.log(`✅ API调用成功`);
        console.log(`   数据源: ${apiData.source}`);
        console.log(`   总规则数: ${apiData.total_rules}`);
        console.log(`   文书类型数: ${apiData.document_types?.length || 0}`);
        console.log('');
        
        const rulesByDocumentType = apiData.rules_by_document_type || {};
        
        // 2. 测试每个文书类型的规则获取
        console.log('📋 测试各文书类型的质控规则获取:');
        
        for (const category of documentCategories) {
            const rules = getApplicableRules(category.category_code, rulesByDocumentType);
            const status = rules.length > 0 ? '✅' : '❌';
            
            console.log(`   ${status} ${category.category_name} (${category.category_code}): ${rules.length} 条规则`);
            
            // 显示前3条规则的详情
            if (rules.length > 0) {
                rules.slice(0, 3).forEach((rule, index) => {
                    console.log(`      ${index + 1}. ${rule.name}`);
                    console.log(`         类别: ${rule.category} | 严重程度: ${rule.defect_level}`);
                });
                if (rules.length > 3) {
                    console.log(`      ... 还有 ${rules.length - 3} 条规则`);
                }
            }
            console.log('');
        }
        
        // 3. 重点验证入院记录
        const admissionRules = getApplicableRules('admission_record', rulesByDocumentType);
        
        console.log('🎯 入院记录质控规则详细验证:');
        console.log(`   规则总数: ${admissionRules.length}`);
        
        if (admissionRules.length > 0) {
            console.log('   ✅ 修复成功！入院记录现在可以正确获取质控规则');
            
            // 按类别统计
            const categoryStats = {};
            const severityStats = {};
            
            admissionRules.forEach(rule => {
                categoryStats[rule.category] = (categoryStats[rule.category] || 0) + 1;
                severityStats[rule.defect_level] = (severityStats[rule.defect_level] || 0) + 1;
            });
            
            console.log('\n   📊 规则分类统计:');
            Object.entries(categoryStats).forEach(([category, count]) => {
                console.log(`      ${category}: ${count} 条`);
            });
            
            console.log('\n   📊 严重程度统计:');
            Object.entries(severityStats).forEach(([severity, count]) => {
                console.log(`      ${severity}: ${count} 条`);
            });
            
            console.log('\n   📝 示例规则:');
            admissionRules.slice(0, 5).forEach((rule, index) => {
                console.log(`      ${index + 1}. ${rule.name}`);
                console.log(`         描述: ${rule.description}`);
                console.log(`         类别: ${rule.category} | 严重程度: ${rule.defect_level}`);
                console.log('');
            });
            
        } else {
            console.log('   ❌ 修复失败！入院记录仍然无法获取质控规则');
        }
        
        // 4. 总结
        console.log('🏁 验证总结:');
        const totalRulesFound = documentCategories.reduce((sum, cat) => {
            return sum + getApplicableRules(cat.category_code, rulesByDocumentType).length;
        }, 0);
        
        console.log(`   总共找到 ${totalRulesFound} 条质控规则`);
        console.log(`   入院记录规则: ${admissionRules.length} 条 ${admissionRules.length > 0 ? '✅' : '❌'}`);
        
        if (admissionRules.length > 0) {
            console.log('\n🎉 修复验证成功！');
            console.log('   现在在医疗质控系统中选择"入院记录"文书类型时，');
            console.log('   应该能够正确显示相关的质控检查项目了。');
        } else {
            console.log('\n❌ 修复验证失败！');
            console.log('   需要进一步检查问题原因。');
        }
        
    } catch (error) {
        console.error('❌ 验证过程中出现错误:', error.message);
    }
}

// 运行验证
verifyFix();
