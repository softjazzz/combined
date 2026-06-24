<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50/30 p-6">
    <!-- 页面标题 -->
    <div class="mb-8">
      <div class="flex items-center space-x-3 mb-2">
        <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
          <SettingOutlined class="text-white text-lg" />
        </div>
        <h1 class="text-2xl font-bold text-gray-800">
          账户设置
        </h1>
      </div>
      <p class="text-gray-600">
        管理您的账户安全和偏好设置
      </p>
    </div>

    <div class="max-w-4xl mx-auto">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- 侧边导航 -->
        <div class="lg:col-span-1">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <nav class="space-y-2">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                class="w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200"
                :class="activeTab === tab.key 
                  ? 'bg-blue-50 text-blue-600 border border-blue-200' 
                  : 'text-gray-600 hover:bg-gray-50'"
                @click="activeTab = tab.key"
              >
                <component
                  :is="tab.icon"
                  class="text-lg"
                />
                <span>{{ tab.label }}</span>
              </button>
            </nav>
          </div>
        </div>

        <!-- 主要内容区域 -->
        <div class="lg:col-span-3">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <!-- 安全设置 -->
            <div v-if="activeTab === 'security'">
              <h3 class="text-lg font-semibold text-gray-800 mb-6">
                安全设置
              </h3>
              
              <!-- 修改密码 -->
              <div class="mb-8">
                <h4 class="text-md font-medium text-gray-700 mb-4">
                  修改密码
                </h4>
                <form
                  class="space-y-4"
                  @submit.prevent="handleChangePassword"
                >
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">当前密码</label>
                    <input
                      v-model="passwordForm.currentPassword"
                      type="password"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="请输入当前密码"
                    >
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">新密码</label>
                    <input
                      v-model="passwordForm.newPassword"
                      type="password"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="请输入新密码"
                    >
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">确认新密码</label>
                    <input
                      v-model="passwordForm.confirmPassword"
                      type="password"
                      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="请再次输入新密码"
                    >
                  </div>
                  <button
                    type="submit"
                    :disabled="passwordLoading"
                    class="px-6 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                  >
                    <span
                      v-if="passwordLoading"
                      class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                    />
                    <span>{{ passwordLoading ? '修改中...' : '修改密码' }}</span>
                  </button>
                </form>
              </div>

              <!-- 两步验证 -->
              <div class="mb-8 pb-8 border-b border-gray-100">
                <h4 class="text-md font-medium text-gray-700 mb-4">
                  两步验证
                </h4>
                <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <div class="font-medium text-gray-800">
                      短信验证
                    </div>
                    <div class="text-sm text-gray-600">
                      通过手机短信接收验证码
                    </div>
                  </div>
                  <button
                    class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    :class="twoFactorEnabled ? 'bg-blue-600' : 'bg-gray-200'"
                    @click="toggleTwoFactor"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                      :class="twoFactorEnabled ? 'translate-x-6' : 'translate-x-1'"
                    />
                  </button>
                </div>
              </div>
            </div>

            <!-- 通知设置 -->
            <div v-if="activeTab === 'notifications'">
              <h3 class="text-lg font-semibold text-gray-800 mb-6">
                通知设置
              </h3>
              
              <div class="space-y-6">
                <div
                  v-for="notification in notificationSettings"
                  :key="notification.key"
                  class="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div>
                    <div class="font-medium text-gray-800">
                      {{ notification.title }}
                    </div>
                    <div class="text-sm text-gray-600">
                      {{ notification.description }}
                    </div>
                  </div>
                  <button
                    class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    :class="notification.enabled ? 'bg-blue-600' : 'bg-gray-200'"
                    @click="toggleNotification(notification.key)"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                      :class="notification.enabled ? 'translate-x-6' : 'translate-x-1'"
                    />
                  </button>
                </div>
              </div>
            </div>

            <!-- 偏好设置 -->
            <div v-if="activeTab === 'preferences'">
              <h3 class="text-lg font-semibold text-gray-800 mb-6">
                偏好设置
              </h3>
              
              <div class="space-y-6">
                <!-- 语言设置 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">语言</label>
                  <select
                    v-model="preferences.language"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="zh-CN">
                      简体中文
                    </option>
                    <option value="en-US">
                      English
                    </option>
                  </select>
                </div>

                <!-- 时区设置 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">时区</label>
                  <select
                    v-model="preferences.timezone"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="Asia/Shanghai">
                      北京时间 (UTC+8)
                    </option>
                    <option value="UTC">
                      协调世界时 (UTC)
                    </option>
                  </select>
                </div>

                <!-- 主题设置 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">主题</label>
                  <div class="grid grid-cols-3 gap-3">
                    <button
                      v-for="theme in themes"
                      :key="theme.key"
                      class="p-3 border rounded-lg text-center transition-all duration-200"
                      :class="preferences.theme === theme.key 
                        ? 'border-blue-500 bg-blue-50 text-blue-600' 
                        : 'border-gray-300 hover:border-gray-400'"
                      @click="preferences.theme = theme.key"
                    >
                      <div class="text-sm font-medium">
                        {{ theme.name }}
                      </div>
                    </button>
                  </div>
                </div>

                <button
                  :disabled="preferencesLoading"
                  class="px-6 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                  @click="savePreferences"
                >
                  <span
                    v-if="preferencesLoading"
                    class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                  />
                  <span>{{ preferencesLoading ? '保存中...' : '保存设置' }}</span>
                </button>
              </div>
            </div>

            <!-- 隐私设置 -->
            <div v-if="activeTab === 'privacy'">
              <h3 class="text-lg font-semibold text-gray-800 mb-6">
                隐私设置
              </h3>
              
              <div class="space-y-6">
                <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <div class="flex items-start space-x-3">
                    <div class="w-5 h-5 text-yellow-600 mt-0.5">
                      ⚠️
                    </div>
                    <div>
                      <div class="font-medium text-yellow-800">
                        数据隐私提醒
                      </div>
                      <div class="text-sm text-yellow-700 mt-1">
                        您的个人信息受到严格保护，仅用于医疗质控系统的正常运行。
                      </div>
                    </div>
                  </div>
                </div>

                <div class="space-y-4">
                  <div
                    v-for="privacy in privacySettings"
                    :key="privacy.key"
                    class="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <div class="font-medium text-gray-800">
                        {{ privacy.title }}
                      </div>
                      <div class="text-sm text-gray-600">
                        {{ privacy.description }}
                      </div>
                    </div>
                    <button
                      class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                      :class="privacy.enabled ? 'bg-blue-600' : 'bg-gray-200'"
                      @click="togglePrivacy(privacy.key)"
                    >
                      <span
                        class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                        :class="privacy.enabled ? 'translate-x-6' : 'translate-x-1'"
                      />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { 
  SettingOutlined, 
  SafetyCertificateOutlined, 
  BellOutlined, 
  UserOutlined, 
  EyeOutlined 
} from '@ant-design/icons-vue'

// 响应式数据
const activeTab = ref('security')
const passwordLoading = ref(false)
const preferencesLoading = ref(false)
const twoFactorEnabled = ref(false)

// 标签页配置
const tabs = [
  { key: 'security', label: '安全设置', icon: SafetyCertificateOutlined },
  { key: 'notifications', label: '通知设置', icon: BellOutlined },
  { key: 'preferences', label: '偏好设置', icon: UserOutlined },
  { key: 'privacy', label: '隐私设置', icon: EyeOutlined }
]

// 密码表单
const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 通知设置
const notificationSettings = reactive([
  {
    key: 'qc_alerts',
    title: '质控提醒',
    description: '接收质控检查结果和异常提醒',
    enabled: true
  },
  {
    key: 'system_updates',
    title: '系统更新',
    description: '接收系统更新和维护通知',
    enabled: true
  },
  {
    key: 'email_notifications',
    title: '邮件通知',
    description: '通过邮件接收重要通知',
    enabled: false
  }
])

// 偏好设置
const preferences = reactive({
  language: 'zh-CN',
  timezone: 'Asia/Shanghai',
  theme: 'light'
})

// 主题选项
const themes = [
  { key: 'light', name: '浅色' },
  { key: 'dark', name: '深色' },
  { key: 'auto', name: '自动' }
]

// 隐私设置
const privacySettings = reactive([
  {
    key: 'profile_visibility',
    title: '个人资料可见性',
    description: '允许其他用户查看您的基本信息',
    enabled: true
  },
  {
    key: 'activity_tracking',
    title: '活动跟踪',
    description: '记录您的系统使用情况以改善服务',
    enabled: true
  }
])

// 修改密码
const handleChangePassword = async () => {
  if (!passwordForm.currentPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
    message.error('请填写所有密码字段')
    return
  }

  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    message.error('新密码和确认密码不匹配')
    return
  }

  if (passwordForm.newPassword.length < 6) {
    message.error('新密码长度至少6位')
    return
  }

  try {
    passwordLoading.value = true
    
    // 这里应该调用API修改密码
    // await AuthService.changePassword(passwordForm)
    
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    message.success('密码修改成功')
    
    // 清空表单
    Object.assign(passwordForm, {
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    })
  } catch (error) {
    console.error('修改密码失败:', error)
    message.error('修改密码失败，请重试')
  } finally {
    passwordLoading.value = false
  }
}

// 切换两步验证
const toggleTwoFactor = () => {
  twoFactorEnabled.value = !twoFactorEnabled.value
  message.success(twoFactorEnabled.value ? '两步验证已开启' : '两步验证已关闭')
}

// 切换通知设置
const toggleNotification = (key: string) => {
  const setting = notificationSettings.find(s => s.key === key)
  if (setting) {
    setting.enabled = !setting.enabled
    message.success(`${setting.title}${setting.enabled ? '已开启' : '已关闭'}`)
  }
}

// 保存偏好设置
const savePreferences = async () => {
  try {
    preferencesLoading.value = true
    
    // 这里应该调用API保存偏好设置
    // await UserService.updatePreferences(preferences)
    
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    message.success('偏好设置保存成功')
  } catch (error) {
    console.error('保存偏好设置失败:', error)
    message.error('保存失败，请重试')
  } finally {
    preferencesLoading.value = false
  }
}

// 切换隐私设置
const togglePrivacy = (key: string) => {
  const setting = privacySettings.find(s => s.key === key)
  if (setting) {
    setting.enabled = !setting.enabled
    message.success(`${setting.title}${setting.enabled ? '已开启' : '已关闭'}`)
  }
}
</script>

<style scoped>
/* 使用 Tailwind CSS 进行样式设计，移除所有自定义CSS */
</style>
