#!/usr/bin/env node

/**
 * 调试前端API调用问题
 */

const fetch = require('node-fetch');

const API_BASE_URL = 'http://localhost:8001';

async function debugFrontendAPI() {
  console.log('🔧 调试前端API调用问题');
  console.log('============================================================');

  try {
    // 步骤1：检查后端服务状态
    console.log('🔍 步骤1：检查后端服务状态...');
    try {
      const healthResponse = await fetch(`${API_BASE_URL}/api/health`);
      console.log(`📊 健康检查状态: ${healthResponse.status} ${healthResponse.statusText}`);
      if (healthResponse.ok) {
        const healthData = await healthResponse.json();
        console.log('✅ 后端服务正常运行');
        console.log(`  服务状态: ${healthData.status}`);
      }
    } catch (error) {
      console.log('❌ 后端服务连接失败:', error.message);
      return;
    }

    // 步骤2：测试登录
    console.log('\n🔐 步骤2：测试用户登录...');
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

    console.log(`📊 登录响应状态: ${loginResponse.status} ${loginResponse.statusText}`);
    
    if (!loginResponse.ok) {
      const errorText = await loginResponse.text();
      console.log(`❌ 登录失败: ${errorText}`);
      return;
    }

    const loginResult = await loginResponse.json();
    const token = loginResult.access_token;
    console.log('✅ 登录成功!');
    console.log(`  Token: ${token.substring(0, 20)}...`);

    // 步骤3：检查localStorage中的token格式
    console.log('\n🔑 步骤3：检查token存储格式...');
    console.log('前端应该检查以下key:');
    console.log('  - medqc_access_token (推荐)');
    console.log('  - token (备用)');
    console.log('  - access_token (备用)');

    // 步骤4：测试病历列表API
    console.log('\n📋 步骤4：测试病历列表API...');
    const recordsResponse = await fetch(`${API_BASE_URL}/api/records?page=1&page_size=10`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    console.log(`📊 病历列表响应状态: ${recordsResponse.status} ${recordsResponse.statusText}`);
    
    if (!recordsResponse.ok) {
      const errorText = await recordsResponse.text();
      console.log(`❌ 获取病历列表失败: ${errorText}`);
      return;
    }

    const recordsResult = await recordsResponse.json();
    console.log('✅ 获取病历列表成功!');
    console.log(`  总记录数: ${recordsResult.total}`);
    console.log(`  当前页记录数: ${recordsResult.data.length}`);
    
    // 步骤5：分析数据结构
    console.log('\n🔍 步骤5：分析返回的数据结构...');
    if (recordsResult.data && recordsResult.data.length > 0) {
      const firstRecord = recordsResult.data[0];
      console.log('📄 第一条记录的字段:');
      Object.keys(firstRecord).forEach(key => {
        console.log(`  - ${key}: ${typeof firstRecord[key]} = ${JSON.stringify(firstRecord[key]).substring(0, 50)}...`);
      });
      
      // 检查LLM解析记录
      const llmRecords = recordsResult.data.filter(r => r.record_type === 'LLM解析结果');
      console.log(`\n🤖 LLM解析记录数量: ${llmRecords.length}`);
      
      if (llmRecords.length > 0) {
        console.log('📋 LLM解析记录示例:');
        const llmRecord = llmRecords[0];
        console.log(`  ID: ${llmRecord.id}`);
        console.log(`  患者姓名: ${llmRecord.patient_name}`);
        console.log(`  科室: ${llmRecord.department}`);
        console.log(`  状态: ${llmRecord.status}`);
        console.log(`  类型: ${llmRecord.record_type}`);
        console.log(`  创建时间: ${llmRecord.created_at}`);
      }
    } else {
      console.log('⚠️  没有返回任何记录数据');
    }

    // 步骤6：模拟前端数据转换
    console.log('\n🔄 步骤6：模拟前端数据转换...');
    const transformedRecords = recordsResult.data.map(record => ({
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

    console.log(`✅ 转换后的记录数量: ${transformedRecords.length}`);
    if (transformedRecords.length > 0) {
      console.log('📄 转换后的第一条记录:');
      const firstTransformed = transformedRecords[0];
      Object.keys(firstTransformed).forEach(key => {
        console.log(`  - ${key}: ${JSON.stringify(firstTransformed[key])}`);
      });
    }

    // 步骤7：检查前端期望的数据格式
    console.log('\n📋 步骤7：前端数据格式检查...');
    console.log('前端期望的字段:');
    console.log('  - id: 记录ID');
    console.log('  - recordNumber: 记录编号');
    console.log('  - recordName: 记录名称');
    console.log('  - patientName: 患者姓名');
    console.log('  - department: 科室');
    console.log('  - primaryDiagnosis: 主要诊断');
    console.log('  - status: 状态');
    console.log('  - importMethod: 导入方式');
    console.log('  - createdAt: 创建时间');

    console.log('\n✅ 数据转换完成，前端应该能正常显示');

  } catch (error) {
    console.error('❌ 调试过程中出现错误:', error.message);
  }

  console.log('\n============================================================');
  console.log('🔧 调试完成');
  console.log('');
  console.log('📝 前端调试建议:');
  console.log('1. 检查浏览器控制台是否有JavaScript错误');
  console.log('2. 检查Network标签页中的API请求是否成功');
  console.log('3. 检查localStorage中是否有正确的token');
  console.log('4. 检查Vue组件的数据绑定是否正确');
  console.log('5. 检查认证状态管理是否正常工作');
}

// 运行调试
debugFrontendAPI();
