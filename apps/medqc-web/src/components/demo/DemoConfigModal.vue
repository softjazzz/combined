<template>
  <a-modal
    v-model:open="visible"
    title="演示配置"
    width="600px"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :label-col="{ span: 8 }"
      :wrapper-col="{ span: 16 }"
    >
      <!-- 自动推进 -->
      <a-form-item label="自动推进">
        <a-switch
          v-model:checked="formData.autoAdvance"
          checked-children="开"
          un-checked-children="关"
        />
        <div class="form-item-hint">
          启用后，每个步骤完成后自动进入下一步
        </div>
      </a-form-item>

      <!-- 步骤延迟 -->
      <a-form-item label="步骤延迟（毫秒）">
        <a-input-number
          v-model:value="formData.stepDelay"
          :min="0"
          :max="10000"
          :step="100"
          style="width: 100%"
        />
        <div class="form-item-hint">
          每个步骤之间的延迟时间（0-10000ms）
        </div>
      </a-form-item>

      <!-- 显示日志 -->
      <a-form-item label="显示日志">
        <a-switch
          v-model:checked="formData.showLogs"
          checked-children="显示"
          un-checked-children="隐藏"
        />
        <div class="form-item-hint">
          在界面上显示详细的执行日志
        </div>
      </a-form-item>

      <!-- 模拟延迟 -->
      <a-form-item label="模拟延迟">
        <a-switch
          v-model:checked="formData.simulateDelay"
          checked-children="开"
          un-checked-children="关"
        />
        <div class="form-item-hint">
          模拟真实的API调用延迟，便于演示
        </div>
      </a-form-item>

      <!-- 调试模式 -->
      <a-form-item label="调试模式">
        <a-switch
          v-model:checked="formData.debugMode"
          checked-children="开"
          un-checked-children="关"
        />
        <div class="form-item-hint">
          启用后在控制台输出详细的调试信息
        </div>
      </a-form-item>

      <!-- 自动通知 -->
      <a-form-item label="自动生成通知">
        <a-switch
          v-model:checked="formData.autoNotifications"
          checked-children="开"
          un-checked-children="关"
        />
        <div class="form-item-hint">
          分析完成后自动生成模拟通知
        </div>
      </a-form-item>

      <!-- 通知间隔 -->
      <a-form-item
        label="通知间隔（秒）"
        v-if="formData.autoNotifications"
      >
        <a-input-number
          v-model:value="formData.notificationInterval"
          :min="1"
          :max="60"
          :step="1"
          style="width: 100%"
        />
        <div class="form-item-hint">
          自动生成通知的时间间隔（1-60秒）
        </div>
      </a-form-item>

      <!-- 状态持久化 -->
      <a-form-item label="状态持久化">
        <a-switch
          v-model:checked="formData.persistState"
          checked-children="开"
          un-checked-children="关"
        />
        <div class="form-item-hint">
          自动保存演示状态到本地存储
        </div>
      </a-form-item>

      <!-- 状态过期时间 -->
      <a-form-item
        label="状态过期（小时）"
        v-if="formData.persistState"
      >
        <a-input-number
          v-model:value="formData.stateExpiryHours"
          :min="1"
          :max="168"
          :step="1"
          style="width: 100%"
        />
        <div class="form-item-hint">
          保存的状态过期时间（1-168小时，即1周）
        </div>
      </a-form-item>
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="handleReset">
          <ReloadOutlined />
          恢复默认
        </a-button>
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" @click="handleOk">确定</a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'

// Props
interface Props {
  open: boolean
  config: DemoConfig
}

interface DemoConfig {
  autoAdvance: boolean
  stepDelay: number
  showLogs: boolean
  simulateDelay: boolean
  debugMode: boolean
  autoNotifications: boolean
  notificationInterval: number
  persistState: boolean
  stateExpiryHours: number
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:config': [config: DemoConfig]
}>()

// 内部状态
const visible = ref(props.open)
const formRef = ref()
const formData = ref<DemoConfig>({ ...props.config })

// 默认配置
const defaultConfig: DemoConfig = {
  autoAdvance: true,
  stepDelay: 1000,
  showLogs: true,
  simulateDelay: true,
  debugMode: false,
  autoNotifications: true,
  notificationInterval: 3,
  persistState: true,
  stateExpiryHours: 24
}

// 监听 props 变化
watch(() => props.open, (newVal) => {
  visible.value = newVal
  if (newVal) {
    formData.value = { ...props.config }
  }
})

watch(visible, (newVal) => {
  emit('update:open', newVal)
})

// 处理确定
const handleOk = () => {
  emit('update:config', { ...formData.value })
  
  // 同步调试模式到 localStorage
  if (formData.value.debugMode) {
    localStorage.setItem('demo-debug-mode', 'true')
  } else {
    localStorage.removeItem('demo-debug-mode')
  }
  
  visible.value = false
}

// 处理取消
const handleCancel = () => {
  visible.value = false
}

// 恢复默认
const handleReset = () => {
  formData.value = { ...defaultConfig }
}
</script>

<style scoped lang="less">
.form-item-hint {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 4px;
}
</style>

