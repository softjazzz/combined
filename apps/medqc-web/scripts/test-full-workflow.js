"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * 完整工作流程测试脚本
 * 测试病案上传到分析的完整流程
 */
const dotenv_1 = require("dotenv");
const medical_records_1 = require("../src/api/medical-records");
const qc_analysis_api_1 = require("../src/api/qc-analysis-api");
// 加载环境变量
(0, dotenv_1.config)();
// 测试用病历数据
const testMedicalRecordData = {
    patient_name: '测试患者',
    patient_age: 45,
    patient_gender: 'M',
    department: '心内科',
    admission_date: '2024-01-15',
    record_type: 'inpatient',
    content: `
入院记录

患者姓名：测试患者    性别：男    年龄：45岁
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
`
};
async function testFullWorkflow() {
    console.log('🧪 开始完整工作流程测试...\n');
    try {
        // 1. 健康检查
        console.log('1️⃣ DeepSeek API健康检查...');
        const health = await (0, qc_analysis_api_1.healthCheck)();
        console.log(`   状态: ${health.status}`);
        console.log(`   消息: ${health.message}`);
        if (health.status !== 'ok') {
            console.log('❌ API连接失败，跳过后续测试');
            return;
        }
        console.log('✅ API连接正常\n');
        // 2. 创建医疗记录
        console.log('2️⃣ 创建医疗记录...');
        const createResult = await (0, medical_records_1.createMedicalRecord)(testMedicalRecordData);
        if (createResult.error || !createResult.data) {
            throw new Error(`创建记录失败: ${createResult.error?.message}`);
        }
        const record = createResult.data;
        console.log(`✅ 记录创建成功`);
        console.log(`   记录ID: ${record.id}`);
        console.log(`   患者: ${record.patient_name}`);
        console.log(`   状态: ${record.status}\n`);
        // 3. 进行AI分析
        console.log('3️⃣ 开始AI质控分析...');
        const analysisStart = Date.now();
        const analysisResult = await (0, qc_analysis_api_1.analyzeRecord)(record.id);
        const analysisTime = Date.now() - analysisStart;
        console.log(`⏱️  分析耗时: ${analysisTime}ms`);
        if (analysisResult.error) {
            throw new Error(`分析失败: ${analysisResult.error.message}`);
        }
        if (!analysisResult.data) {
            throw new Error('分析结果为空');
        }
        const analysis = analysisResult.data;
        console.log('✅ 分析完成');
        console.log(`   总体评分: ${analysis.overallScore}分`);
        console.log(`   等级评定: ${analysis.grade}级`);
        console.log(`   完整性: ${analysis.categoryScores.completeness}分`);
        console.log(`   一致性: ${analysis.categoryScores.consistency}分`);
        console.log(`   合理性: ${analysis.categoryScores.rationality}分`);
        console.log(`   及时性: ${analysis.categoryScores.timeliness}分`);
        console.log(`   建议数量: ${analysis.suggestions.length}条\n`);
        // 4. 验证记录状态更新
        console.log('4️⃣ 验证记录状态更新...');
        const recordsResult = await (0, medical_records_1.getMedicalRecords)({ limit: 1 });
        if (recordsResult.error) {
            throw new Error(`获取记录失败: ${recordsResult.error.message}`);
        }
        const updatedRecord = recordsResult.data.find(r => r.id === record.id);
        if (!updatedRecord) {
            throw new Error('未找到更新后的记录');
        }
        console.log('✅ 记录状态验证成功');
        console.log(`   状态: ${updatedRecord.status}`);
        console.log(`   评分: ${updatedRecord.qc_score}分`);
        console.log(`   等级: ${updatedRecord.qc_grade}级\n`);
        // 5. 显示分析建议
        if (analysis.suggestions.length > 0) {
            console.log('5️⃣ AI分析建议:');
            analysis.suggestions.forEach((suggestion, index) => {
                console.log(`   ${index + 1}. ${suggestion}`);
            });
            console.log('');
        }
        // 6. 总结
        console.log('🎉 完整工作流程测试成功！');
        console.log('='.repeat(50));
        console.log('📊 测试总结:');
        console.log(`   ✅ 记录创建: 成功`);
        console.log(`   ✅ AI分析: 成功`);
        console.log(`   ✅ 状态更新: 成功`);
        console.log(`   ✅ 数据库保存: 成功`);
        console.log(`   ⏱️  总耗时: ${Date.now() - analysisStart}ms`);
        console.log(`   📈 最终评分: ${analysis.overallScore}分 (${analysis.grade}级)`);
    }
    catch (error) {
        console.error('❌ 工作流程测试失败:', error);
        process.exit(1);
    }
}
// 运行测试
testFullWorkflow().catch(console.error);
