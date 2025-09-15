/**
 * 认证持久化功能测试脚本
 * 在浏览器控制台中运行此脚本来测试认证功能
 */

console.log('🧪 开始测试认证持久化功能...')

// 测试用户凭据
const testCredentials = {
  email: 'admin@yibao.com',
  password: 'admin123'
}

// 测试函数
async function testAuthPersistence() {
  console.log('📋 测试计划:')
  console.log('1. 清除现有认证状态')
  console.log('2. 测试登录功能')
  console.log('3. 验证token存储')
  console.log('4. 测试页面刷新后状态保持')
  console.log('5. 测试token自动刷新')
  console.log('6. 测试登出功能')
  console.log('')

  // 步骤1: 清除现有认证状态
  console.log('🧹 步骤1: 清除现有认证状态')
  localStorage.clear()
  console.log('✅ 本地存储已清除')

  // 步骤2: 测试登录功能
  console.log('\n🔐 步骤2: 测试登录功能')
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testCredentials)
    })

    if (response.ok) {
      const data = await response.json()
      console.log('✅ 登录成功:', data)
      
      // 检查token是否存储
      const storedToken = localStorage.getItem('yibao_access_token')
      const storedUser = localStorage.getItem('yibao_user')
      const storedAuth = localStorage.getItem('yibao_authenticated')
      
      console.log('📦 存储检查:')
      console.log('- Access Token:', storedToken ? '✅ 已存储' : '❌ 未存储')
      console.log('- User Info:', storedUser ? '✅ 已存储' : '❌ 未存储')
      console.log('- Auth Flag:', storedAuth ? '✅ 已存储' : '❌ 未存储')
      
      if (storedUser) {
        try {
          const userInfo = JSON.parse(storedUser)
          console.log('👤 用户信息:', userInfo)
        } catch (e) {
          console.log('❌ 用户信息解析失败')
        }
      }
    } else {
      console.log('❌ 登录失败:', response.status, response.statusText)
    }
  } catch (error) {
    console.log('❌ 登录请求失败:', error)
  }

  // 步骤3: 测试认证状态检查
  console.log('\n🔍 步骤3: 测试认证状态检查')
  try {
    const response = await fetch('/api/auth/me', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('yibao_access_token')}`
      }
    })

    if (response.ok) {
      const userData = await response.json()
      console.log('✅ 用户信息获取成功:', userData)
    } else {
      console.log('❌ 用户信息获取失败:', response.status)
    }
  } catch (error) {
    console.log('❌ 用户信息请求失败:', error)
  }

  // 步骤4: 模拟页面刷新测试
  console.log('\n🔄 步骤4: 模拟页面刷新测试')
  console.log('请手动刷新页面，然后检查:')
  console.log('- 用户是否仍然保持登录状态')
  console.log('- 是否能正常访问需要认证的页面')
  console.log('- 控制台是否显示"从缓存恢复用户状态"')

  // 步骤5: 测试token有效性
  console.log('\n⏰ 步骤5: 检查token有效性')
  const token = localStorage.getItem('yibao_access_token')
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      const exp = new Date(payload.exp * 1000)
      const now = new Date()
      const timeLeft = exp.getTime() - now.getTime()
      
      console.log('🕐 Token信息:')
      console.log('- 过期时间:', exp.toLocaleString())
      console.log('- 剩余时间:', Math.round(timeLeft / 1000 / 60), '分钟')
      console.log('- 是否有效:', timeLeft > 0 ? '✅ 有效' : '❌ 已过期')
    } catch (e) {
      console.log('❌ Token解析失败')
    }
  }

  console.log('\n✨ 测试完成！请检查以上结果并手动验证页面刷新功能。')
}

// 运行测试
testAuthPersistence()

// 提供手动测试函数
window.testLogin = async () => {
  console.log('🔐 手动登录测试...')
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(testCredentials)
  })
  const data = await response.json()
  console.log('登录结果:', data)
}

window.testLogout = async () => {
  console.log('🚪 手动登出测试...')
  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('yibao_access_token')}`
    }
  })
  console.log('登出结果:', response.status)
  localStorage.clear()
  console.log('本地存储已清除')
}

window.checkAuthStatus = () => {
  console.log('📊 当前认证状态:')
  console.log('- Token:', localStorage.getItem('yibao_access_token') ? '✅' : '❌')
  console.log('- User:', localStorage.getItem('yibao_user') ? '✅' : '❌')
  console.log('- Auth Flag:', localStorage.getItem('yibao_authenticated') ? '✅' : '❌')
}

console.log('🛠️ 可用的手动测试函数:')
console.log('- testLogin() - 测试登录')
console.log('- testLogout() - 测试登出')
console.log('- checkAuthStatus() - 检查认证状态')
