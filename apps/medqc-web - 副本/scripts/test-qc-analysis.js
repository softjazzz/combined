"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * 病案质控分析测试脚本
 * 使用阿里云百炼DeepSeek V3进行分析
 */
const dotenv_1 = require("dotenv");
// 加载环境变量
(0, dotenv_1.config)();
const API_KEY = 'sk-f1fa15b00fb042a9a80943a40e142daf';
const BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
const MODEL = 'deepseek-v3';
// 测试用病历内容
const testMedicalRecord = `
入院记录

患者姓名：张三    性别：男    年龄：45岁
入院时间：2024年1月15日 14:30
主诉：胸痛3小时

现病史：
患者于3小时前无明显诱因出现胸痛，疼痛位于胸骨后，呈压榨性疼痛，向左臂放射，伴有憋气、出汗，无恶心呕吐。
患者既往有高血压病史10年，糖尿病病史5年，长期服用降压药物和降糖药物。
否认冠心病病史，否认心肌梗死病史。

体格检查：
T: 36.8°C, P: 95次/分, R: 20次/分, BP: 150/90mmHg
神志清楚，精神欠佳，面色苍白，口唇无紫绀。
心界不大，心率95次/分，律齐，未闻及病理性杂音。
双肺呼吸音清，未闻及干湿性啰音。
腹软，无压痛，肝脾肋下未触及。

辅助检查：
心电图：窦性心律，ST段轻度压低
心肌酶：CK-MB 25 IU/L（正常值<25），肌钙蛋白I 0.15 ng/ml（正常值<0.04）

初步诊断：
1. 急性心肌梗死？
2. 高血压病
3. 糖尿病

治疗方案：
1. 给予阿司匹林 300mg口服
2. 氯吡格雷 300mg口服  
3. 低分子肝素抗凝
4. 他汀类药物调脂
5. 硝酸甘油缓解胸痛
6. 监护观察，必要时行冠脉造影
`;
// 质控分析提示词
const QC_ANALYSIS_PROMPT = `
你是一名专业的医疗质控专家，请对以下病案进行全面的质量控制分析。

请从以下四个维度进行评估：

1. **完整性评估**：
   - 检查病案记录是否完整
   - 必需信息是否齐全
   - 缺失哪些重要内容

2. **一致性评估**：
   - 症状、体征、检查结果是否一致
   - 诊断与临床表现是否匹配
   - 治疗方案与诊断是否相符

3. **合理性评估**：
   - 诊断是否合理
   - 治疗方案是否恰当
   - 用药是否规范

4. **及时性评估**：
   - 诊疗流程是否及时
   - 关键检查是否及时完成
   - 治疗是否及时启动

请以JSON格式返回分析结果，包含：
- completeness_score: 完整性评分(0-100)
- consistency_score: 一致性评分(0-100)  
- rationality_score: 合理性评分(0-100)
- timeliness_score: 及时性评分(0-100)
- overall_score: 总体评分(0-100)
- grade: 等级评定(A/B/C)
- issues: 发现的问题列表
- suggestions: 改进建议列表

病案内容：
${testMedicalRecord}
`;
async function testQCAnalysis() {
    console.log('🏥 开始病案质控分析测试...\n');
    try {
        console.log('📋 分析病案内容:');
        console.log(testMedicalRecord.substring(0, 200) + '...\n');
        console.log('⚡ 调用AI进行质控分析...');
        const startTime = Date.now();
        const response = await fetch(`${BASE_URL}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`
            },
            body: JSON.stringify({
                model: MODEL,
                messages: [
                    {
                        role: 'system',
                        content: '你是一名专业的医疗质控专家，擅长分析病案质量并提供改进建议。请严格按照要求的JSON格式返回分析结果。'
                    },
                    {
                        role: 'user',
                        content: QC_ANALYSIS_PROMPT
                    }
                ],
                max_tokens: 2000,
                temperature: 0.1
            })
        });
        const analysisTime = Date.now() - startTime;
        console.log(`⏱️  分析耗时: ${analysisTime}ms`);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ API请求失败:');
            console.error(errorText);
            return;
        }
        const result = await response.json();
        const aiResponse = result.choices?.[0]?.message?.content || '';
        console.log('\n📊 AI质控分析结果:');
        console.log('='.repeat(50));
        console.log(aiResponse);
        // 尝试解析JSON结果
        try {
            const jsonMatch = aiResponse.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const analysisResult = JSON.parse(jsonMatch[0]);
                console.log('\n✅ 解析成功的结构化结果:');
                console.log(`📈 总体评分: ${analysisResult.overall_score}分`);
                console.log(`🏆 等级评定: ${analysisResult.grade}级`);
                console.log(`📝 完整性: ${analysisResult.completeness_score}分`);
                console.log(`🔄 一致性: ${analysisResult.consistency_score}分`);
                console.log(`💡 合理性: ${analysisResult.rationality_score}分`);
                console.log(`⏰ 及时性: ${analysisResult.timeliness_score}分`);
                if (analysisResult.issues && analysisResult.issues.length > 0) {
                    console.log('\n⚠️  发现的问题:');
                    analysisResult.issues.forEach((issue, index) => {
                        console.log(`${index + 1}. ${issue}`);
                    });
                }
                if (analysisResult.suggestions && analysisResult.suggestions.length > 0) {
                    console.log('\n💡 改进建议:');
                    analysisResult.suggestions.forEach((suggestion, index) => {
                        console.log(`${index + 1}. ${suggestion}`);
                    });
                }
            }
        }
        catch (parseError) {
            console.log('\n⚠️  JSON解析失败，显示原始结果');
        }
        if (result.usage) {
            console.log('\n📊 Token使用情况:');
            console.log(`输入Token: ${result.usage.prompt_tokens}`);
            console.log(`输出Token: ${result.usage.completion_tokens}`);
            console.log(`总Token: ${result.usage.total_tokens}`);
        }
    }
    catch (error) {
        console.error('❌ 分析失败:', error);
    }
}
// 运行测试
testQCAnalysis().catch(console.error);
