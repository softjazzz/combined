#!/usr/bin/env node

/**
 * 测试前端登录并设置localStorage
 */

const fetch = require('node-fetch');

const API_BASE_URL = 'http://localhost:8001';

async function testFrontendLogin() {
  console.log('🔐 测试前端登录并设置localStorage');
  console.log('============================================================');

  try {
    // 步骤1：登录获取token
    console.log('📤 步骤1：用户登录...');
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
    console.log(`  Token: ${token.substring(0, 30)}...`);

    // 步骤2：提供前端localStorage设置指令
    console.log('\n🔧 步骤2：前端localStorage设置指令');
    console.log('请在浏览器控制台中执行以下命令来设置token:');
    console.log('');
    console.log(`localStorage.setItem('medqc_access_token', '${token}');`);
    console.log(`localStorage.setItem('token', '${token}');`);
    console.log(`localStorage.setItem('access_token', '${token}');`);
    console.log('');
    console.log('然后刷新页面，应该能看到病历列表');

    // 步骤3：验证token有效性
    console.log('\n🔍 步骤3：验证token有效性...');
    const testResponse = await fetch(`${API_BASE_URL}/api/records?page=1&page_size=5`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    console.log(`📊 测试API响应状态: ${testResponse.status} ${testResponse.statusText}`);
    
    if (testResponse.ok) {
      const testResult = await testResponse.json();
      console.log('✅ Token有效，API调用成功!');
      console.log(`  返回记录数: ${testResult.data.length}`);
      console.log(`  总记录数: ${testResult.total}`);
    } else {
      const errorText = await testResponse.text();
      console.log(`❌ Token验证失败: ${errorText}`);
    }

  } catch (error) {
    console.error('❌ 测试过程中出现错误:', error.message);
  }

  console.log('\n============================================================');
  console.log('🔧 测试完成');
  console.log('');
  console.log('📝 前端调试步骤:');
  console.log('1. 打开浏览器开发者工具');
  console.log('2. 在控制台中执行上面的localStorage设置命令');
  console.log('3. 刷新页面 http://localhost:3000/dashboard/medical-records');
  console.log('4. 检查控制台日志，查看API调用情况');
  console.log('5. 检查Network标签页，确认API请求成功');
}

// 运行测试
testFrontendLogin();
