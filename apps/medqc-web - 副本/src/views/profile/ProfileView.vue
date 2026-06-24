<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50/30 p-6">
    <!-- 页面标题 -->
    <div class="mb-8">
      <div class="flex items-center space-x-3 mb-2">
        <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
          <UserOutlined class="text-white text-lg" />
        </div>
        <h1 class="text-2xl font-bold text-gray-800">
          个人资料
        </h1>
      </div>
      <p class="text-gray-600">
        管理您的个人信息和账户详情
      </p>
    </div>

    <div class="max-w-4xl mx-auto">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 用户头像和基本信息卡片 -->
        <div class="lg:col-span-1">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="text-center">
              <!-- 用户头像 -->
              <div class="relative inline-block mb-4">
                <div class="w-24 h-24 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center shadow-lg">
                  <UserOutlined class="text-white text-3xl" />
                </div>
                <!-- 在线状态指示器 -->
                <div class="absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 rounded-full border-4 border-white" />
              </div>
              
              <h3 class="text-xl font-semibold text-gray-800 mb-1">
                {{ authStore.userName }}
              </h3>
              <p class="text-gray-600 mb-2">
                {{ getRoleLabel(authStore.userRoles?.[0]) }}
              </p>
              
              <!-- 角色标签 -->
              <div
                class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium"
                :class="{
                  'bg-orange-100 text-orange-800': authStore.hasRole('admin'),
                  'bg-green-100 text-green-800': authStore.hasRole('qc_manager'),
                  'bg-blue-100 text-blue-800': authStore.hasRole('doctor'),
                  'bg-purple-100 text-purple-800': authStore.hasRole('nurse')
                }"
              >
                {{ getRoleLabel(authStore.userRoles?.[0]) }}
              </div>
            </div>
            
            <!-- 快速统计 -->
            <div class="mt-6 pt-6 border-t border-gray-100">
              <div class="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div class="text-2xl font-bold text-blue-600">
                    {{ stats.loginCount }}
                  </div>
                  <div class="text-xs text-gray-500">
                    登录次数
                  </div>
                </div>
                <div>
                  <div class="text-2xl font-bold text-green-600">
                    {{ stats.activeDays }}
                  </div>
                  <div class="text-xs text-gray-500">
                    活跃天数
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 详细信息表单 -->
        <div class="lg:col-span-2">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-lg font-semibold text-gray-800">
                基本信息
              </h3>
              <button 
                class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                :class="isEditing ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' : 'bg-blue-500 text-white hover:bg-blue-600'"
                @click="toggleEdit"
              >
                {{ isEditing ? '取消编辑' : '编辑资料' }}
              </button>
            </div>

            <form
              class="space-y-6"
              @submit.prevent="handleSave"
            >
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- 姓名 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">姓名</label>
                  <input
                    v-model="formData.name"
                    :disabled="!isEditing"
                    type="text"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="请输入姓名"
                  >
                </div>

                <!-- 工号 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">工号</label>
                  <input
                    v-model="formData.employeeId"
                    :disabled="!isEditing"
                    type="text"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="请输入工号"
                  >
                </div>

                <!-- 邮箱 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">邮箱</label>
                  <input
                    v-model="formData.email"
                    :disabled="!isEditing"
                    type="email"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="请输入邮箱"
                  >
                </div>

                <!-- 手机号 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">手机号</label>
                  <input
                    v-model="formData.phone"
                    :disabled="!isEditing"
                    type="tel"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="请输入手机号"
                  >
                </div>

                <!-- 科室 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">科室</label>
                  <select
                    v-model="formData.department"
                    :disabled="!isEditing"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                  >
                    <option value="">
                      请选择科室
                    </option>
                    <option value="internal">
                      内科
                    </option>
                    <option value="surgery">
                      外科
                    </option>
                    <option value="pediatrics">
                      儿科
                    </option>
                    <option value="obstetrics">
                      妇产科
                    </option>
                    <option value="emergency">
                      急诊科
                    </option>
                    <option value="icu">
                      重症医学科
                    </option>
                    <option value="qc">
                      质控科
                    </option>
                  </select>
                </div>

                <!-- 职位 -->
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-2">职位</label>
                  <input
                    v-model="formData.position"
                    :disabled="!isEditing"
                    type="text"
                    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                    placeholder="请输入职位"
                  >
                </div>
              </div>

              <!-- 保存按钮 -->
              <div
                v-if="isEditing"
                class="flex justify-end space-x-3 pt-6 border-t border-gray-100"
              >
                <button
                  type="button"
                  class="px-6 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-all duration-200"
                  @click="toggleEdit"
                >
                  取消
                </button>
                <button
                  type="submit"
                  :disabled="loading"
                  class="px-6 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  <span
                    v-if="loading"
                    class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                  />
                  <span>{{ loading ? '保存中...' : '保存更改' }}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UserOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 响应式数据
const isEditing = ref(false)
const loading = ref(false)

// 统计数据
const stats = reactive({
  loginCount: 156,
  activeDays: 89
})

// 表单数据
const formData = reactive({
  name: '',
  employeeId: '',
  email: '',
  phone: '',
  department: '',
  position: ''
})

// 角色标签映射
const getRoleLabel = (role: string) => {
  const roleMap: Record<string, string> = {
    'admin': '系统管理员',
    'qc_manager': '质控管理员',
    'doctor': '医生',
    'nurse': '护士',
    'medical_staff': '医务人员'
  }
  return roleMap[role] || role
}

// 切换编辑模式
const toggleEdit = () => {
  if (isEditing.value) {
    // 取消编辑，恢复原始数据
    loadUserData()
  }
  isEditing.value = !isEditing.value
}

// 保存用户信息
const handleSave = async () => {
  try {
    loading.value = true
    
    // 这里应该调用API保存用户信息
    // await UserService.updateProfile(formData)
    
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    message.success('个人资料更新成功')
    isEditing.value = false
  } catch (error) {
    console.error('保存失败:', error)
    message.error('保存失败，请重试')
  } finally {
    loading.value = false
  }
}

// 加载用户数据
const loadUserData = () => {
  // 这里应该从API加载用户数据
  // 现在使用模拟数据
  Object.assign(formData, {
    name: authStore.userName || '张医生',
    employeeId: 'DOC001',
    email: 'zhang.doctor@hospital.com',
    phone: '138****8888',
    department: 'internal',
    position: '主治医师'
  })
}

// 生命周期
onMounted(() => {
  loadUserData()
})
</script>

<style scoped>
/* 使用 Tailwind CSS 进行样式设计，移除所有自定义CSS */
</style>
