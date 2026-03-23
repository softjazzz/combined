<template>
  <div class="classification-version-manager">
    <a-card
      title="医疗文书分类算法版本管理"
      class="mb-4"
    >
      <template #extra>
        <a-button
          :loading="loading"
          @click="refreshVersionInfo"
        >
          <template #icon>
            <ReloadOutlined />
          </template>
          刷新
        </a-button>
      </template>

      <!-- 当前版本信息 -->
      <a-descriptions
        title="当前版本信息"
        :column="2"
        bordered
        class="mb-4"
      >
        <a-descriptions-item label="当前版本">
          <a-tag :color="getVersionColor(versionInfo.current_version)">
            {{ versionInfo.current_version_name }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="回退版本">
          <a-tag color="orange">
            {{ versionInfo.fallback_version_name }}
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 版本切换 -->
      <a-card
        title="版本切换"
        size="small"
        class="mb-4"
      >
        <a-radio-group 
          v-model:value="selectedVersion" 
          :disabled="switching"
          @change="onVersionChange"
        >
          <a-space direction="vertical">
            <a-radio 
              v-for="version in availableVersions" 
              :key="version.value"
              :value="version.value"
            >
              <div class="version-option">
                <div class="version-name">
                  {{ version.name }}
                  <a-tag
                    v-if="version.value === versionInfo.current_version"
                    color="green"
                    size="small"
                  >
                    当前
                  </a-tag>
                </div>
                <div class="version-description">
                  {{ version.description }}
                </div>
              </div>
            </a-radio>
          </a-space>
        </a-radio-group>

        <div class="mt-3">
          <a-button 
            type="primary" 
            :loading="switching"
            :disabled="selectedVersion === versionInfo.current_version"
            @click="switchVersion"
          >
            切换到选中版本
          </a-button>
        </div>
      </a-card>

      <!-- 性能统计 -->
      <a-card
        title="性能统计"
        size="small"
      >
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic
              title="总请求数"
              :value="performanceStats.total_requests"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="成功率" 
              :value="performanceStats.success_rate" 
              suffix="%" 
              :precision="1"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="平均处理时间" 
              :value="performanceStats.average_processing_time" 
              suffix="秒"
              :precision="3"
            />
          </a-col>
          <a-col :span="6">
            <a-button
              size="small"
              danger
              @click="resetStats"
            >
              重置统计
            </a-button>
          </a-col>
        </a-row>

        <!-- 版本使用分布 -->
        <div class="mt-4">
          <h4>版本使用分布</h4>
          <a-progress 
            v-for="(count, version) in performanceStats.version_usage" 
            :key="version"
            :percent="(count / performanceStats.total_requests * 100)"
            :format="() => `${version}: ${count}次`"
            class="mb-2"
          />
        </div>
      </a-card>

      <!-- 健康检查 -->
      <a-card
        title="系统健康检查"
        size="small"
        class="mt-4"
      >
        <a-button
          :loading="healthChecking"
          type="dashed"
          block
          @click="runHealthCheck"
        >
          <template #icon>
            <HeartOutlined />
          </template>
          运行健康检查
        </a-button>
        
        <div
          v-if="healthStatus"
          class="mt-3"
        >
          <a-alert 
            :type="healthStatus.status === 'healthy' ? 'success' : 'error'"
            :message="`系统状态: ${healthStatus.status === 'healthy' ? '健康' : '异常'}`"
            show-icon
          />
          <div class="mt-2">
            <a-descriptions
              size="small"
              :column="1"
            >
              <a-descriptions-item label="分类测试">
                <a-tag :color="healthStatus.classification_test ? 'green' : 'red'">
                  {{ healthStatus.classification_test ? '通过' : '失败' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="配置验证">
                <a-tag :color="healthStatus.config_validation.valid ? 'green' : 'red'">
                  {{ healthStatus.config_validation.valid ? '有效' : '无效' }}
                </a-tag>
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </div>
      </a-card>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, HeartOutlined } from '@ant-design/icons-vue'

type ClassificationVersionKey = 'basic' | 'enhanced' | 'advanced'

interface ClassificationVersionInfo {
  current_version: string
  current_version_name: string
  fallback_version: string
  fallback_version_name: string
  available_versions: string[]
  version_descriptions: Record<string, string>
}

interface ClassificationPerformanceStats {
  total_requests: number
  successful_requests: number
  failed_requests: number
  success_rate: number
  average_processing_time: number
  version_usage: Record<string, number>
}

interface ClassificationHealthStatus {
  status: 'healthy' | 'unhealthy' | string
  classification_test: boolean
  config_validation: {
    valid: boolean
  }
}

// 响应式数据
const loading = ref(false)
const switching = ref(false)
const healthChecking = ref(false)
const selectedVersion = ref('')

const versionInfo = ref<ClassificationVersionInfo>({
  current_version: '',
  current_version_name: '',
  fallback_version: '',
  fallback_version_name: '',
  available_versions: [],
  version_descriptions: {}
})

const performanceStats = ref<ClassificationPerformanceStats>({
  total_requests: 0,
  successful_requests: 0,
  failed_requests: 0,
  success_rate: 0,
  average_processing_time: 0,
  version_usage: {}
})

const healthStatus = ref<ClassificationHealthStatus | null>(null)

// 计算属性
const availableVersions = computed(() => {
  return versionInfo.value.available_versions.map(version => ({
    value: version,
    name: getVersionName(version),
    description: versionInfo.value.version_descriptions[version] || ''
  }))
})

// 方法
const getVersionColor = (version: string) => {
  const colors: Record<ClassificationVersionKey, string> = {
    'basic': 'blue',
    'enhanced': 'green', 
    'advanced': 'purple'
  }
  return version in colors ? colors[version as ClassificationVersionKey] : 'default'
}

const getVersionName = (version: string) => {
  const names: Record<ClassificationVersionKey, string> = {
    'basic': '基础版本',
    'enhanced': '增强版本',
    'advanced': '先进版本'
  }
  return version in names ? names[version as ClassificationVersionKey] : version
}

const refreshVersionInfo = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/enhanced-classification/version/info')
    if (response.ok) {
      versionInfo.value = await response.json()
      selectedVersion.value = versionInfo.value.current_version
    } else {
      message.error('获取版本信息失败')
    }
  } catch (error) {
    message.error('网络错误')
  } finally {
    loading.value = false
  }
}

const refreshPerformanceStats = async () => {
  try {
    const response = await fetch('/api/enhanced-classification/performance/stats')
    if (response.ok) {
      performanceStats.value = await response.json()
    }
  } catch (error) {
    console.error('获取性能统计失败:', error)
  }
}

const switchVersion = async () => {
  if (selectedVersion.value === versionInfo.value.current_version) {
    message.warning('已经是当前版本')
    return
  }

  switching.value = true
  try {
    const response = await fetch('/api/enhanced-classification/version/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: selectedVersion.value })
    })

    const result = await response.json()
    
    if (result.success) {
      message.success(`成功切换到 ${getVersionName(selectedVersion.value)}`)
      await refreshVersionInfo()
      await refreshPerformanceStats()
    } else {
      message.error(result.message || '版本切换失败')
    }
  } catch (error) {
    message.error('网络错误')
  } finally {
    switching.value = false
  }
}

const resetStats = async () => {
  try {
    const response = await fetch('/api/enhanced-classification/performance/reset', {
      method: 'POST'
    })
    
    if (response.ok) {
      message.success('性能统计已重置')
      await refreshPerformanceStats()
    } else {
      message.error('重置失败')
    }
  } catch (error) {
    message.error('网络错误')
  }
}

const runHealthCheck = async () => {
  healthChecking.value = true
  try {
    const response = await fetch('/api/enhanced-classification/health')
    if (response.ok) {
      healthStatus.value = await response.json()
      message.success('健康检查完成')
    } else {
      message.error('健康检查失败')
    }
  } catch (error) {
    message.error('网络错误')
  } finally {
    healthChecking.value = false
  }
}

const onVersionChange = () => {
  // 版本选择变化时的处理
}

// 生命周期
onMounted(async () => {
  await refreshVersionInfo()
  await refreshPerformanceStats()
})
</script>

<style scoped>
.classification-version-manager {
  max-width: 1200px;
  margin: 0 auto;
}

.version-option {
  margin-left: 8px;
}

.version-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.version-description {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}
</style>
