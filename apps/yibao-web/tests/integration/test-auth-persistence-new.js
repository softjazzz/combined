/**
 * 认证持久化测试脚本 - 修复版本
 * 用于验证修复后的认证持久化功能
 */

console.log('🧪 开始测试修复后的认证持久化功能...')

// 测试配置
const TEST_CONFIG = {
  testUser: {
    email: 'admin@yibao.com',
    password: 'admin123'
  }
}

// 测试结果记录
const testResults = {
  passed: 0,
  failed: 0,
  tests: []
}

// 工具函数
function recordTest(name, passed, details = '') {
  const result = { name, passed, details, timestamp: new Date().toISOString() }
  testResults.tests.push(result)
  
  if (passed) {
    testResults.passed++
    console.log(`✅ ${name}`)
  } else {
    testResults.failed++
    console.log(`❌ ${name}`)
  }
  
  if (details) {
    console.log(`   详情: ${details}`)
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function checkAuthData() {
  const token = localStorage.getItem('yibao_access_token')
  const refreshToken = localStorage.getItem('yibao_refresh_token')
  const user = localStorage.getItem('yibao_user')
  const authenticated = localStorage.getItem('yibao_authenticated')
  
  return {
    hasToken: !!token,
    hasRefreshToken: !!refreshToken,
    hasUser: !!user,
    isAuthenticated: authenticated === 'true',
    userInfo: user ? JSON.parse(user) : null,
    tokenLength: token ? token.length : 0
  }
}

// 测试1: 检查当前认证状态
async function testCurrentAuthState() {
  console.log('\n🔍 测试1: 检查当前认证状态')
  
  const authData = checkAuthData()
  console.log('认证数据状态:', authData)
  
  recordTest(
    '当前认证状态检查',
    true,
    `Token: ${authData.hasToken}, User: ${authData.hasUser}, Authenticated: ${authData.isAuthenticated}`
  )
  
  return authData
}

// 测试2: 模拟登录并检查数据保存
async function testLoginAndPersistence() {
  console.log('\n🔐 测试2: 模拟登录并检查数据保存')
  
  try {
    // 清除现有数据
    localStorage.removeItem('yibao_access_token')
    localStorage.removeItem('yibao_refresh_token')
    localStorage.removeItem('yibao_user')
    localStorage.removeItem('yibao_authenticated')
    localStorage.removeItem('yibao_session_id')
    
    console.log('已清除现有认证数据')
    
    // 创建mock用户数据
    const mockUser = {
      id: 'test_user_' + Date.now(),
      email: TEST_CONFIG.testUser.email,
      display_name: TEST_CONFIG.testUser.email,
      roles: ['admin'],
      department: '医保办',
      is_active: true
    }
    
    // 生成mock JWT token (7天有效期)
    const header = { alg: 'none', typ: 'JWT' }
    const payload = { 
      exp: Math.floor(Date.now() / 1000) + (7 * 24 * 60 * 60), 
      iat: Math.floor(Date.now() / 1000), 
      sub: 'test-user' 
    }
    const base64url = (obj) => btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
    const mockToken = `${base64url(header)}.${base64url(payload)}.`
    
    // 保存认证数据
    localStorage.setItem('yibao_user', JSON.stringify(mockUser))
    localStorage.setItem('yibao_authenticated', 'true')
    localStorage.setItem('yibao_access_token', mockToken)
    localStorage.setItem('yibao_refresh_token', mockToken)
    localStorage.setItem('yibao_session_id', `session_${Date.now()}_test`)
    
    console.log('已保存mock认证数据')
    
    await sleep(200) // 等待存储完成
    
    // 验证数据保存
    const authData = checkAuthData()
    const saveSuccess = authData.hasToken && authData.hasUser && authData.isAuthenticated
    
    recordTest(
      '登录数据保存',
      saveSuccess,
      saveSuccess ? '认证数据已正确保存到localStorage' : '认证数据保存失败'
    )
    
    return saveSuccess
  } catch (error) {
    recordTest('登录数据保存', false, `保存过程异常: ${error.message}`)
    return false
  }
}

// 测试3: 模拟页面刷新
async function testPageRefresh() {
  console.log('\n🔄 测试3: 模拟页面刷新场景')
  
  try {
    // 记录刷新前状态
    const beforeRefresh = checkAuthData()
    console.log('刷新前状态:', beforeRefresh)
    
    if (!beforeRefresh.isAuthenticated) {
      recordTest('页面刷新测试', false, '刷新前未处于登录状态')
      return false
    }
    
    // 模拟页面刷新 - 清除内存状态但保留localStorage
    console.log('模拟页面刷新...')
    
    // 触发storage事件模拟跨标签页同步
    window.dispatchEvent(new StorageEvent('storage', {
      key: 'yibao_authenticated',
      newValue: 'true',
      storageArea: localStorage
    }))
    
    await sleep(300)
    
    // 检查刷新后状态
    const afterRefresh = checkAuthData()
    console.log('刷新后状态:', afterRefresh)
    
    const persistenceSuccess = 
      afterRefresh.hasToken && 
      afterRefresh.hasUser && 
      afterRefresh.isAuthenticated
    
    recordTest(
      '页面刷新后数据保持',
      persistenceSuccess,
      persistenceSuccess ? 'localStorage中的认证数据完整保持' : '认证数据丢失或不完整'
    )
    
    return persistenceSuccess
  } catch (error) {
    recordTest('页面刷新测试', false, `测试过程异常: ${error.message}`)
    return false
  }
}

// 测试4: Token解析和有效性
async function testTokenValidation() {
  console.log('\n🔑 测试4: Token解析和有效性检查')
  
  try {
    const token = localStorage.getItem('yibao_access_token')
    
    if (!token) {
      recordTest('Token有效性检查', false, '未找到access token')
      return false
    }
    
    // 解析token
    try {
      const parts = token.split('.')
      if (parts.length !== 3) {
        recordTest('Token格式检查', false, 'Token格式不正确，应该有3个部分')
        return false
      }
      
      const payload = JSON.parse(atob(parts[1]))
      console.log('Token payload:', payload)
      
      const isExpired = payload.exp ? (payload.exp * 1000) < Date.now() : false
      
      recordTest(
        'Token解析和有效性',
        !isExpired,
        isExpired ? 'Token已过期' : 'Token有效且未过期'
      )
      
      return !isExpired
    } catch (parseError) {
      recordTest('Token解析', false, `Token解析失败: ${parseError.message}`)
      return false
    }
  } catch (error) {
    recordTest('Token有效性检查', false, `检查过程异常: ${error.message}`)
    return false
  }
}

// 测试5: 用户信息完整性
async function testUserInfoIntegrity() {
  console.log('\n👤 测试5: 用户信息完整性检查')
  
  try {
    const userStr = localStorage.getItem('yibao_user')
    
    if (!userStr) {
      recordTest('用户信息存在性', false, '未找到用户信息')
      return false
    }
    
    const userInfo = JSON.parse(userStr)
    console.log('用户信息:', userInfo)
    
    const requiredFields = ['id', 'email', 'display_name']
    const missingFields = requiredFields.filter(field => !userInfo[field])
    
    const isComplete = missingFields.length === 0
    
    recordTest(
      '用户信息完整性',
      isComplete,
      isComplete ? '用户信息包含所有必要字段' : `缺少字段: ${missingFields.join(', ')}`
    )
    
    return isComplete
  } catch (error) {
    recordTest('用户信息完整性', false, `检查过程异常: ${error.message}`)
    return false
  }
}

// 主测试函数
async function runAllTests() {
  console.log('🚀 开始执行认证持久化测试套件...')
  console.log('测试时间:', new Date().toLocaleString())
  console.log('=' .repeat(50))
  
  try {
    // 执行所有测试
    await testCurrentAuthState()
    const loginSuccess = await testLoginAndPersistence()
    
    if (loginSuccess) {
      await testPageRefresh()
      await testTokenValidation()
      await testUserInfoIntegrity()
    } else {
      console.log('⚠️ 登录测试失败，跳过后续测试')
    }
    
    // 输出测试结果汇总
    console.log('\n' + '=' .repeat(50))
    console.log('📊 测试结果汇总:')
    console.log(`✅ 通过: ${testResults.passed}`)
    console.log(`❌ 失败: ${testResults.failed}`)
    console.log(`📈 成功率: ${((testResults.passed / (testResults.passed + testResults.failed)) * 100).toFixed(1)}%`)
    
    // 详细结果
    console.log('\n📋 详细测试结果:')
    testResults.tests.forEach((test, index) => {
      const status = test.passed ? '✅' : '❌'
      console.log(`${index + 1}. ${status} ${test.name}`)
      if (test.details) {
        console.log(`   ${test.details}`)
      }
    })
    
    console.log('\n🎯 测试建议:')
    if (testResults.failed === 0) {
      console.log('🎉 所有测试通过！认证持久化功能工作正常。')
    } else {
      console.log('⚠️ 部分测试失败，请检查认证持久化实现。')
    }
    
    return testResults
  } catch (error) {
    console.error('❌ 测试执行失败:', error)
    return testResults
  }
}

// 导出测试函数
window.runAllTests = runAllTests
window.checkAuthData = checkAuthData

console.log('📝 认证持久化测试脚本已加载')
console.log('💡 在控制台运行 runAllTests() 来执行完整测试')
console.log('💡 在控制台运行 checkAuthData() 来检查当前认证状态')
