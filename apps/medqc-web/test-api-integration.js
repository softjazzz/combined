/**
 * API集成测试脚本
 * 测试质控API和病案首页API
 */

const testContent = `首次病程记录

记录时间：2025年10月11日 15:00

一、患者基本信息
姓名：李明
性别：男
年龄：58岁
科室：心内科

二、主诉
反复胸闷、胸痛3天，加重伴气促1天。

三、现病史
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后，持续时间约5-10分钟，休息后可缓解。

四、初步诊断
1. 急性冠脉综合征（ACS）
2. 高血压病 3级 很高危
3. 2型糖尿病`;

// 测试1：四川质控API
async function testQCAPI() {
  console.log('\n=== 测试1：四川质控API ===\n');

  try {
    const response = await fetch('http://127.0.0.1:8001/api/v1/qc/sichuan/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        document_id: 'test-doc-001',
        document_content: testContent,
        document_type: '首次病程记录',
        persist: false,
        prompt_mode: 'plan_a'
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    console.log('✅ 质控API调用成功');
    console.log('响应数据:', JSON.stringify(data, null, 2).substring(0, 500) + '...');

    if (data.data && data.data.evaluation_summary) {
      console.log('\n质控结果摘要:');
      console.log('  - 总规则数:', data.data.evaluation_summary.total_rules);
      console.log('  - 合规率:', data.data.evaluation_summary.compliance_rate + '%');
      console.log('  - 等级:', data.data.evaluation_summary.overall_grade);
      console.log('  - 严重违规:', data.data.evaluation_summary.critical_violations);

      if (data.data.performance_metrics) {
        console.log('  - 处理时间:', data.data.performance_metrics.processing_time.toFixed(2) + '秒');
      }
    }

    return true;
  } catch (error) {
    console.error('❌ 质控API调用失败:', error.message);
    return false;
  }
}

// 测试2：病案首页API
async function testFrontpageAPI() {
  console.log('\n=== 测试2：病案首页生成API ===\n');

  try {
    const response = await fetch('http://127.0.0.1:8001/api/v1/frontpage/auto-generate-draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        visit_id: 'V20251011001',
        documents: [
          {
            type: '入院记录',
            content: testContent
          }
        ]
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    console.log('✅ 病案首页API调用成功');

    if (data.data && data.data.frontpage) {
      console.log('\n病案首页数据:');
      console.log('  - 患者姓名:', data.data.frontpage.basic_info?.patient_name || '-');
      console.log('  - 性别:', data.data.frontpage.basic_info?.gender_text || '-');
      console.log('  - 年龄:', data.data.frontpage.basic_info?.age_years || '-');
      console.log('  - 入院时间:', data.data.frontpage.hospitalization?.admission_datetime || '-');
    }

    return true;
  } catch (error) {
    console.error('❌ 病案首页API调用失败:', error.message);
    return false;
  }
}

// 主测试流程
async function main() {
  console.log('开始API集成测试...');
  console.log('后端地址: http://127.0.0.1:8001');

  const qcResult = await testQCAPI();
  const frontpageResult = await testFrontpageAPI();

  console.log('\n' + '='.repeat(50));
  console.log('测试结果汇总:');
  console.log('  质控API:', qcResult ? '✅ 通过' : '❌ 失败');
  console.log('  病案首页API:', frontpageResult ? '✅ 通过' : '❌ 失败');
  console.log('='.repeat(50) + '\n');

  if (qcResult && frontpageResult) {
    console.log('🎉 所有API测试通过！可以在浏览器中访问演示页面：');
    console.log('   http://localhost:3000/demo/clinical-workstation');
  } else {
    console.log('⚠️ 部分API测试失败，请检查后端服务日志。');
    process.exit(1);
  }
}

main();
