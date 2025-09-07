#!/usr/bin/env node

/**
 * 测试前端病历卡片列表是否能正常显示LLM解析记录
 */

const fetch = require('node-fetch');

const API_BASE_URL = 'http://localhost:8001';

async function testFrontendRecordsList() {
  console.log('🧪 测试前端病历卡片列表显示LLM解析记录');
  console.log('============================================================');

  try {
    // 步骤1：用户登录获取token
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

    // 步骤2：调用前端使用的病历列表接口
    console.log('\n📋 步骤2：获取病历列表（前端接口）...');
    const recordsResponse = await fetch(`${API_BASE_URL}/api/records?page=1&page_size=20`, {
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

    // 步骤3：分析记录类型
    console.log('\n📄 记录详情:');
    let llmRecordsCount = 0;
    
    recordsResult.data.forEach((record, index) => {
      console.log(`  ${index + 1}. ${record.patient_name} (${record.id})`);
      console.log(`     科室: ${record.department}`);
      console.log(`     状态: ${record.status}`);
      console.log(`     类型: ${record.record_type}`);
      console.log(`     创建时间: ${record.created_at}`);
      
      if (record.record_type === 'LLM解析结果') {
        llmRecordsCount++;
      }
      console.log('');
    });

    // 步骤4：验证结果
    console.log(`🔍 LLM解析记录统计: ${llmRecordsCount} 条`);
    
    if (llmRecordsCount > 0) {
      console.log('🎉 找到 LLM解析记录！');
      console.log('✅ 前端病历卡片列表应该能正常显示LLM解析的记录');
    } else {
      console.log('⚠️  没有找到LLM解析记录');
      console.log('❌ 前端病历卡片列表可能无法显示LLM解析的记录');
    }

    // 步骤5：创建一个新的LLM解析记录进行测试
    console.log('\n📤 步骤5：创建新的LLM解析记录进行测试...');
    const testRecord = {
      patient_name: '前端测试患者',
      patient_age: 35,
      patient_gender: '女',
      department: '前端测试科室',
      primary_diagnosis: '前端测试诊断',
      content: '这是前端测试记录，用于验证病历卡片列表显示...',
      method: 'LLM精准解析'
    };

    const createResponse = await fetch(`${API_BASE_URL}/api/medical-records`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testRecord)
    });

    console.log(`📊 创建响应状态: ${createResponse.status} ${createResponse.statusText}`);
    
    if (createResponse.ok) {
      const createResult = await createResponse.json();
      console.log('✅ 创建测试记录成功!');
      console.log(`  记录ID: ${createResult.id}`);
      console.log(`  患者姓名: ${createResult.patient_name}`);
      console.log(`  科室: ${createResult.department}`);
      
      // 步骤6：再次获取列表验证新记录
      console.log('\n🔄 步骤6：再次获取列表验证新记录...');
      const updatedResponse = await fetch(`${API_BASE_URL}/api/records?page=1&page_size=20`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (updatedResponse.ok) {
        const updatedResult = await updatedResponse.json();
        const newLlmCount = updatedResult.data.filter(r => r.record_type === 'LLM解析结果').length;
        console.log(`✅ 更新后的LLM解析记录数: ${newLlmCount} 条`);
        
        if (newLlmCount > llmRecordsCount) {
          console.log('🎉 新记录已成功添加到列表中！');
        }
      }
    } else {
      const errorText = await createResponse.text();
      console.log(`❌ 创建测试记录失败: ${errorText}`);
    }

  } catch (error) {
    console.error('❌ 测试过程中出现错误:', error.message);
  }

  console.log('\n============================================================');
  console.log('🔧 测试完成，请检查上述输出来验证前端显示效果');
}

// 运行测试
testFrontendRecordsList();
