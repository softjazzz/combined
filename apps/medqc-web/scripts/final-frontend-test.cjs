#!/usr/bin/env node

/**
 * 最终前端测试 - 完整模拟前端流程
 */

const fetch = require('node-fetch');

const API_BASE_URL = 'http://localhost:8001';

async function finalFrontendTest() {
  console.log('🎯 最终前端测试 - 完整模拟前端流程');
  console.log('============================================================');

  try {
    // 步骤1：登录获取token
    console.log('🔐 步骤1：用户登录...');
    const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: 'admin@medqc.com',
        password: 'admin123'
      })
    });

    if (!loginResponse.ok) {
      console.log(`❌ 登录失败: ${loginResponse.status}`);
      return;
    }

    const loginResult = await loginResponse.json();
    const token = loginResult.access_token;
    console.log('✅ 登录成功!');

    // 步骤2：模拟前端的API调用（完全按照前端代码逻辑）
    console.log('\n📡 步骤2：模拟前端API调用...');
    
    // 构建查询参数（模拟前端逻辑）
    const params = new URLSearchParams();
    params.append('page', '1');
    params.append('page_size', '10');

    const apiUrl = `${API_BASE_URL}/api/records?${params.toString()}`;
    console.log('📋 API URL:', apiUrl);

    const headers = {
      'Content-Type': 'application/json'
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    console.log('📋 请求头:', headers);
    
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers
    });

    console.log(`📊 API响应状态: ${response.status} ${response.statusText}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ API调用失败:', errorText);
      return;
    }

    const result = await response.json();
    console.log('📊 API返回的数据:', {
      total: result.total,
      dataLength: result.data ? result.data.length : 0,
      hasData: !!result.data
    });

    // 步骤3：模拟前端数据转换（完全按照前端代码逻辑）
    console.log('\n🔄 步骤3：模拟前端数据转换...');
    
    if (!result.data || !Array.isArray(result.data)) {
      console.error('❌ API返回的数据格式不正确:', result);
      return;
    }

    console.log(`📋 获取到 ${result.data.length} 条记录`);

    // 转换数据格式以适配现有UI - 适配medical_records表结构
    const transformedRecords = result.data.map((record) => ({
      id: record.id,
      recordNumber: record.record_number || record.id,
      recordName: `${record.patient_name}的病历记录`,
      patientName: record.patient_name || '未知患者',
      department: record.department || '未知科室',
      primaryDiagnosis: record.diagnosis_primary || record.primary_diagnosis || '未知诊断',
      majorSurgery: record.major_surgery || '无',
      qualityPointIds: [],
      createdBy: record.created_by || '系统',
      lastModifiedBy: record.updated_by || record.created_by || '系统',
      createdAt: record.created_at,
      status: record.status,
      importMethod: record.record_type === 'LLM解析结果' ? 'smart_import' : 'manual',
      aiConfidence: record.ai_confidence_score || 0,
      documentsCount: Array.isArray(record.documents) ? record.documents.length : 0
    }));

    console.log('🔄 转换后的记录数据:');
    transformedRecords.forEach((record, index) => {
      console.log(`  ${index + 1}. ${record.patientName} (${record.id})`);
      console.log(`     科室: ${record.department}`);
      console.log(`     状态: ${record.status}`);
      console.log(`     导入方式: ${record.importMethod}`);
      console.log(`     创建时间: ${record.createdAt}`);
      console.log('');
    });

    // 步骤4：分析问题
    console.log('🔍 步骤4：问题分析...');
    
    const llmRecords = transformedRecords.filter(r => r.importMethod === 'smart_import');
    console.log(`🤖 LLM解析记录数量: ${llmRecords.length}`);
    
    if (transformedRecords.length > 0) {
      console.log('✅ 数据转换成功，前端应该能显示记录');
      console.log('');
      console.log('📋 前端显示预期:');
      console.log(`  - 总记录数: ${transformedRecords.length}`);
      console.log(`  - LLM解析记录: ${llmRecords.length}`);
      console.log(`  - 分页总数: ${result.total}`);
      console.log('');
      
      if (llmRecords.length > 0) {
        console.log('🎉 找到LLM解析记录，前端应该能正常显示！');
        console.log('');
        console.log('📄 LLM解析记录示例:');
        const firstLlm = llmRecords[0];
        console.log(`  患者: ${firstLlm.patientName}`);
        console.log(`  科室: ${firstLlm.department}`);
        console.log(`  诊断: ${firstLlm.primaryDiagnosis}`);
        console.log(`  状态: ${firstLlm.status}`);
      }
    } else {
      console.log('❌ 没有记录数据，前端会显示空白');
    }

    // 步骤5：前端调试建议
    console.log('\n🔧 步骤5：前端调试建议');
    console.log('如果前端仍然显示空白，请检查:');
    console.log('1. 浏览器控制台是否有JavaScript错误');
    console.log('2. Network标签页中API请求是否成功');
    console.log('3. Vue组件的响应式数据是否正确更新');
    console.log('4. 认证状态是否正确初始化');
    console.log('');
    console.log('🔑 在浏览器控制台中执行:');
    console.log(`localStorage.setItem('medqc_access_token', '${token}');`);
    console.log('然后刷新页面');

  } catch (error) {
    console.error('❌ 测试过程中出现错误:', error.message);
  }

  console.log('\n============================================================');
  console.log('🎯 最终测试完成');
}

// 运行测试
finalFrontendTest();
