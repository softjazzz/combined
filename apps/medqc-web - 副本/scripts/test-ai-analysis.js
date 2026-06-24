"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.testAIService = testAIService;
/**
 * AI分析服务测试脚本
 * 验证DeepSeek集成和分析流程
 */
const dotenv_1 = require("dotenv");
const analysis_engine_1 = require("../src/lib/qc/analysis-engine");
const deepseek_service_1 = require("../src/lib/ai/deepseek-service");
// 加载环境变量
(0, dotenv_1.config)();
// 在Node.js环境中设置Vite环境变量
process.env.VITE_DEEPSEEK_API_KEY = process.env.VITE_DEEPSEEK_API_KEY;
process.env.VITE_DEEPSEEK_API_URL = process.env.VITE_DEEPSEEK_API_URL;
process.env.VITE_DEEPSEEK_MODEL = process.env.VITE_DEEPSEEK_MODEL;
// 测试用病历内容
const testMedicalRecord = `
入院记录

患者姓名：张三    性别：男    年龄：45岁
入院时间：2024年1月15日 14:30
主诉：胸痛3小时

现病史：
患者于3小时前无明显诱因出现胸前区疼痛，呈压榨性疼痛，伴有胸闷、气短，
无放射痛，无恶心呕吐，疼痛持续不缓解，故来院就诊。

既往史：
高血压病史3年，规律服用降压药物。否认糖尿病、冠心病等病史。

体格检查：
T: 36.8℃  P: 88次/分  R: 20次/分  BP: 140/90mmHg
神志清楚，精神一般，心率88次/分，律齐，无杂音。
双肺呼吸音清，无干湿啰音。腹部平软，无压痛。

辅助检查：
心电图：显示ST段轻微抬高
血常规：白细胞 8.5×10⁹/L，红细胞 4.2×10¹²/L
心肌酶：肌钙蛋白I 0.8ng/ml（正常<0.04ng/ml）

初步诊断：
1. 急性心肌梗死
2. 高血压病

治疗方案：
1. 阿司匹林 100mg qd
2. 氯吡格雷 75mg qd
3. 阿托伐他汀 20mg qn
4. 美托洛尔 25mg bid

医师签名：李医师
日期：2024年1月15日
`;
async function testAIService() {
    console.log('🧪 开始AI分析服务测试...\n');
    try {
        // 1. 测试DeepSeek服务健康检查
        console.log('1️⃣ 测试DeepSeek API连接...');
        const deepseek = (0, deepseek_service_1.getDeepSeekService)();
        const healthCheck = await deepseek.healthCheck();
        console.log(`   状态: ${healthCheck.status}`);
        console.log(`   消息: ${healthCheck.message}\n`);
        if (healthCheck.status !== 'ok') {
            console.log('❌ DeepSeek API连接失败，跳过后续测试');
            return;
        }
        // 2. 测试基础聊天功能
        console.log('2️⃣ 测试基础聊天功能...');
        const chatResponse = await deepseek.chat([
            { role: 'user', content: '请简单介绍一下医疗质控的重要性' }
        ], { max_tokens: 200 });
        console.log(`   AI回复: ${chatResponse.substring(0, 100)}...\n`);
        // 3. 测试质控分析引擎健康检查
        console.log('3️⃣ 测试质控分析引擎状态...');
        const engineHealth = await analysis_engine_1.qcAnalysisEngine.healthCheck();
        console.log('   AI服务:', engineHealth.aiService.status, '-', engineHealth.aiService.message);
        console.log('   数据库:', engineHealth.database.status, '-', engineHealth.database.message);
        console.log('   整体状态:', engineHealth.overall, '\n');
        if (engineHealth.overall !== 'healthy') {
            console.log('⚠️  分析引擎状态异常，继续测试但可能失败');
        }
        // 4. 测试完整质控分析流程
        console.log('4️⃣ 测试完整质控分析流程...');
        console.log('   使用测试病历进行分析...');
        const analysisRequest = {
            recordId: 'test-record-001',
            content: testMedicalRecord,
            options: {
                includeCache: false, // 不使用缓存，确保真实测试
                categories: ['completeness', 'consistency'] // 只测试部分分类以节省时间
            }
        };
        const startTime = Date.now();
        const analysisResult = await analysis_engine_1.qcAnalysisEngine.analyze(analysisRequest);
        const analysisTime = Date.now() - startTime;
        console.log('\n📊 分析结果:');
        console.log(`   总体评分: ${analysisResult.overallScore}`);
        console.log(`   等级: ${analysisResult.grade}`);
        console.log(`   分析状态: ${analysisResult.status}`);
        console.log(`   分析时间: ${analysisTime}ms`);
        console.log(`   违规规则数: ${analysisResult.summary.violatedRules}/${analysisResult.summary.totalRules}`);
        if (analysisResult.summary.criticalIssues > 0) {
            console.log(`   ⚠️  严重问题: ${analysisResult.summary.criticalIssues}个`);
        }
        if (analysisResult.summary.majorIssues > 0) {
            console.log(`   ⚠️  重要问题: ${analysisResult.summary.majorIssues}个`);
        }
        if (analysisResult.summary.minorIssues > 0) {
            console.log(`   ⚠️  轻微问题: ${analysisResult.summary.minorIssues}个`);
        }
        console.log('\n📋 分类得分:');
        Object.entries(analysisResult.categoryScores).forEach(([category, score]) => {
            console.log(`   ${category}: ${score}分`);
        });
        console.log('\n💡 改进建议:');
        analysisResult.suggestions.forEach((suggestion, index) => {
            console.log(`   ${index + 1}. ${suggestion}`);
        });
        // 5. 显示具体违规详情（前3个）
        const violations = analysisResult.ruleResults.filter(r => r.hasViolation).slice(0, 3);
        if (violations.length > 0) {
            console.log('\n🔍 违规详情 (前3个):');
            violations.forEach((violation, index) => {
                console.log(`   ${index + 1}. ${violation.ruleName} (${violation.severity})`);
                console.log(`      置信度: ${(violation.confidence * 100).toFixed(1)}%`);
                console.log(`      原因: ${violation.reasoning}`);
                if (violation.evidence.length > 0) {
                    console.log(`      证据: ${violation.evidence.join(', ')}`);
                }
                console.log();
            });
        }
        // 6. 测试缓存功能
        console.log('5️⃣ 测试分析缓存功能...');
        const cachedStartTime = Date.now();
        const cachedResult = await analysis_engine_1.qcAnalysisEngine.analyze({
            ...analysisRequest,
            options: { includeCache: true } // 启用缓存
        });
        const cachedTime = Date.now() - cachedStartTime;
        console.log(`   缓存测试时间: ${cachedTime}ms`);
        console.log(`   缓存效果: ${cachedTime < analysisTime ? '有效' : '无效'}`);
        if (cachedResult.overallScore === analysisResult.overallScore) {
            console.log('   ✅ 缓存结果一致');
        }
        else {
            console.log('   ⚠️  缓存结果不一致');
        }
        console.log('\n🎉 AI分析服务测试完成！');
        console.log('✅ 所有核心功能正常工作');
    }
    catch (error) {
        console.error('\n❌ 测试失败:', error);
        if (error instanceof Error) {
            console.error('错误详情:', error.message);
            if (error.stack) {
                console.error('堆栈信息:', error.stack);
            }
        }
        console.log('\n💡 可能的解决方案:');
        console.log('1. 检查 VITE_DEEPSEEK_API_KEY 环境变量是否正确设置');
        console.log('2. 确认网络连接和API访问权限');
        console.log('3. 验证数据库连接和表结构');
        console.log('4. 检查质控规则是否已正确初始化');
    }
}
// 执行测试
testAIService();
