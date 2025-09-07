<template>
  <div class="avatar-upload">
    <div class="flex items-center gap-4">
      <!-- 当前头像显示 -->
      <div class="relative">
        <div 
          class="w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-600 flex items-center justify-center shadow-lg"
          :class="{ 'ring-4 ring-cyan-400/30': uploading }"
        >
          <img 
            v-if="currentAvatar" 
            :src="currentAvatar" 
            :alt="userName || '用户头像'"
            class="w-full h-full object-cover"
          />
          <div v-else class="text-white text-2xl font-bold">
            {{ avatarInitial }}
          </div>
        </div>
        
        <!-- 上传进度环 -->
        <div 
          v-if="uploading" 
          class="absolute inset-0 flex items-center justify-center"
        >
          <div class="w-24 h-24 rounded-full border-4 border-transparent border-t-cyan-400 animate-spin"></div>
        </div>
      </div>

      <!-- 上传控制区域 -->
      <div class="flex-1">
        <div class="mb-2">
          <h4 class="text-sm font-medium text-slate-200">个人头像</h4>
          <p class="text-xs text-slate-400">支持 JPG、PNG 格式，文件大小不超过 2MB</p>
        </div>

        <div class="flex gap-2">
          <!-- 上传按钮 -->
          <a-upload
            :custom-request="handleUpload"
            :show-upload-list="false"
            :before-upload="beforeUpload"
            accept="image/jpeg,image/jpg,image/png"
          >
            <a-button 
              size="small" 
              :loading="uploading"
              class="bg-cyan-500/20 border-cyan-400/30 text-cyan-300 hover:bg-cyan-500/30"
            >
              <UploadOutlined />
              {{ uploading ? '上传中...' : '选择图片' }}
            </a-button>
          </a-upload>

          <!-- 删除按钮 -->
          <a-button 
            v-if="currentAvatar && !isDefaultAvatar"
            size="small" 
            danger
            @click="handleRemove"
            class="bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30"
          >
            <DeleteOutlined />
            删除
          </a-button>

          <!-- 重置为默认头像 -->
          <a-button 
            v-if="currentAvatar && !isDefaultAvatar"
            size="small"
            @click="handleReset"
            class="bg-slate-500/20 border-slate-400/30 text-slate-300 hover:bg-slate-500/30"
          >
            <ReloadOutlined />
            重置
          </a-button>
        </div>

        <!-- 上传状态提示 -->
        <div v-if="uploadStatus" class="mt-2">
          <div 
            v-if="uploadStatus.type === 'success'" 
            class="flex items-center gap-1 text-xs text-emerald-400"
          >
            <CheckCircleOutlined />
            {{ uploadStatus.message }}
          </div>
          <div 
            v-else-if="uploadStatus.type === 'error'" 
            class="flex items-center gap-1 text-xs text-red-400"
          >
            <ExclamationCircleOutlined />
            {{ uploadStatus.message }}
          </div>
          <div 
            v-else-if="uploadStatus.type === 'info'" 
            class="flex items-center gap-1 text-xs text-blue-400"
          >
            <InfoCircleOutlined />
            {{ uploadStatus.message }}
          </div>
        </div>
      </div>
    </div>

    <!-- 头像预设选择 -->
    <div v-if="showPresets" class="mt-6">
      <div class="mb-3">
        <h5 class="text-sm font-medium text-slate-200 mb-1">选择预设头像</h5>
        <p class="text-xs text-slate-400">或者从下方预设头像中选择一个</p>
      </div>
      
      <div class="grid grid-cols-6 gap-3">
        <div
          v-for="(preset, index) in presetAvatars"
          :key="index"
          class="w-12 h-12 rounded-full overflow-hidden cursor-pointer transition-all duration-200 hover:scale-110 hover:ring-2 hover:ring-cyan-400/50"
          :class="{ 'ring-2 ring-cyan-400': currentAvatar === preset.url }"
          @click="selectPreset(preset)"
        >
          <img 
            :src="preset.url" 
            :alt="preset.name"
            class="w-full h-full object-cover"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { 
  UploadOutlined, 
  DeleteOutlined, 
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'
import type { UploadRequestOption } from 'ant-design-vue/es/upload/interface'

interface Props {
  modelValue?: string
  userName?: string
  showPresets?: boolean
  maxSize?: number // MB
}

const props = withDefaults(defineProps<Props>(), {
  showPresets: true,
  maxSize: 2
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'upload-success': [url: string]
  'upload-error': [error: string]
}>()

// 状态
const uploading = ref(false)
const uploadStatus = ref<{
  type: 'success' | 'error' | 'info'
  message: string
} | null>(null)

// 当前头像
const currentAvatar = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

// 是否为默认头像
const isDefaultAvatar = computed(() => {
  return !currentAvatar.value || presetAvatars.some(preset => preset.url === currentAvatar.value)
})

// 头像首字母
const avatarInitial = computed(() => {
  if (props.userName) {
    return props.userName.charAt(0).toUpperCase()
  }
  return 'U'
})

// 预设头像列表
const presetAvatars = [
  { name: '医生1', url: '/avatars/doctor-1.png' },
  { name: '医生2', url: '/avatars/doctor-2.png' },
  { name: '护士1', url: '/avatars/nurse-1.png' },
  { name: '护士2', url: '/avatars/nurse-2.png' },
  { name: '管理员1', url: '/avatars/admin-1.png' },
  { name: '管理员2', url: '/avatars/admin-2.png' },
  { name: '质控员1', url: '/avatars/qc-1.png' },
  { name: '质控员2', url: '/avatars/qc-2.png' },
  { name: '通用1', url: '/avatars/generic-1.png' },
  { name: '通用2', url: '/avatars/generic-2.png' },
  { name: '通用3', url: '/avatars/generic-3.png' },
  { name: '通用4', url: '/avatars/generic-4.png' }
]

// 上传前验证
const beforeUpload = (file: File) => {
  // 检查文件类型
  const isValidType = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)
  if (!isValidType) {
    message.error('只支持 JPG、PNG 格式的图片')
    return false
  }

  // 检查文件大小
  const isValidSize = file.size / 1024 / 1024 < props.maxSize
  if (!isValidSize) {
    message.error(`图片大小不能超过 ${props.maxSize}MB`)
    return false
  }

  return true
}

// 处理上传
const handleUpload = async (options: UploadRequestOption) => {
  const { file } = options
  
  try {
    uploading.value = true
    uploadStatus.value = { type: 'info', message: '正在上传头像...' }

    // 模拟上传过程
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 创建本地预览URL
    const reader = new FileReader()
    reader.onload = (e) => {
      const url = e.target?.result as string
      currentAvatar.value = url
      
      uploadStatus.value = { type: 'success', message: '头像上传成功' }
      emit('upload-success', url)
      
      // 3秒后清除状态提示
      setTimeout(() => {
        uploadStatus.value = null
      }, 3000)
    }
    reader.readAsDataURL(file as File)

  } catch (error) {
    console.error('头像上传失败:', error)
    uploadStatus.value = { type: 'error', message: '头像上传失败，请重试' }
    emit('upload-error', error instanceof Error ? error.message : '上传失败')
    
    // 5秒后清除错误提示
    setTimeout(() => {
      uploadStatus.value = null
    }, 5000)
  } finally {
    uploading.value = false
  }
}

// 删除头像
const handleRemove = () => {
  currentAvatar.value = ''
  uploadStatus.value = { type: 'info', message: '头像已删除' }
  
  setTimeout(() => {
    uploadStatus.value = null
  }, 2000)
}

// 重置为默认头像
const handleReset = () => {
  currentAvatar.value = ''
  uploadStatus.value = { type: 'info', message: '已重置为默认头像' }
  
  setTimeout(() => {
    uploadStatus.value = null
  }, 2000)
}

// 选择预设头像
const selectPreset = (preset: typeof presetAvatars[0]) => {
  currentAvatar.value = preset.url
  uploadStatus.value = { type: 'success', message: `已选择 ${preset.name}` }
  
  setTimeout(() => {
    uploadStatus.value = null
  }, 2000)
}

// 监听上传状态变化
watch(uploadStatus,  (newStatus) => {
  if (newStatus?.type === 'error') {
    message.error(newStatus.message)
  } else if (newStatus?.type === 'success') {
    message.success(newStatus.message)
  }
}, { deep: true })
</script>

<style scoped>
.avatar-upload {
  @apply p-4 rounded-xl bg-white/5 border border-white/10;
}

/* 上传按钮样式优化 */
:deep(.ant-btn) {
  border-radius: 0.5rem;
  font-size: 12px;
  height: 32px;
  padding: 0 12px;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 头像容器动画 */
.w-20.h-20 {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.w-20.h-20:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 25px rgba(6, 182, 212, 0.3);
}

/* 预设头像网格动画 */
.grid > div {
  transition: all 0.2s ease-out;
}

.grid > div:hover {
  box-shadow: 0 4px 15px rgba(6, 182, 212, 0.4);
}

/* 状态提示动画 */
.mt-2 > div {
  animation: slideInUp 0.3s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 上传进度环动画 */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
