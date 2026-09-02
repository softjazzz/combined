<template>
  <div class="ds-root product-activation-panel">
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          产品激活
        </h2>
        <p class="ds-section-desc">
          私有化部署使用离线激活码。激活过程不访问互联网，激活码只在本机验证和保存。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body">
            <a-alert
              :type="alertType"
              :message="statusMessage"
              show-icon
              class="activation-alert"
            />

            <a-descriptions
              v-if="status.status === 'active'"
              :column="2"
              bordered
              size="small"
              class="activation-details"
            >
              <a-descriptions-item label="客户">
                {{ status.customer || '—' }}
              </a-descriptions-item>
              <a-descriptions-item label="版本">
                {{ status.edition || '—' }}
              </a-descriptions-item>
              <a-descriptions-item label="序列号">
                {{ status.serial || '—' }}
              </a-descriptions-item>
              <a-descriptions-item label="到期日期">
                {{ formatDate(status.expires_at) }}
              </a-descriptions-item>
            </a-descriptions>

            <div class="activation-input">
              <label for="product-activation-code">输入激活码</label>
              <a-textarea
                id="product-activation-code"
                v-model:value="activationCode"
                :disabled="activating"
                :rows="4"
                :maxlength="20000"
                allow-clear
                placeholder="请粘贴发行方提供的离线激活码"
              />
              <div class="activation-input__hint">
                激活码不会在页面中回显或展示完整内容。
              </div>
            </div>

            <a-space>
              <a-button
                :loading="loading"
                @click="loadStatus"
              >
                <template #icon>
                  <ReloadOutlined />
                </template>
                刷新状态
              </a-button>
              <a-button
                type="primary"
                :loading="activating"
                :disabled="!activationCode.trim()"
                @click="handleActivate"
              >
                <template #icon>
                  <SafetyCertificateOutlined />
                </template>
                激活产品
              </a-button>
            </a-space>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'

import {
  activateProduct,
  getProductActivationStatus,
  type ProductActivationState,
  type ProductActivationStatus,
} from '@/api/productActivation'

const loading = ref(false)
const activating = ref(false)
const activationCode = ref('')
const status = ref<ProductActivationStatus>({ status: 'invalid', required: false })

const statusMessage = computed(() => {
  const messages: Record<ProductActivationState, string> = {
    not_required: '当前环境未启用产品激活门禁',
    missing: '产品尚未激活，请输入激活码',
    active: `产品已激活，有效期至 ${formatDate(status.value.expires_at)}`,
    expired: '产品激活已过期，请导入新的激活码',
    invalid: '本地激活状态无效，请重新导入激活码',
    not_configured: '本机未配置激活验证公钥，请联系发行方',
  }
  return messages[status.value.status]
})

const alertType = computed(() => {
  if (status.value.status === 'active' || status.value.status === 'not_required') return 'success'
  if (status.value.status === 'missing') return 'warning'
  return 'error'
})

function formatDate(value?: string): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN')
}

async function loadStatus() {
  loading.value = true
  const result = await getProductActivationStatus()
  if (result.success && result.data) {
    status.value = result.data
  } else {
    message.error(result.message || '获取产品激活状态失败')
  }
  loading.value = false
}

async function handleActivate() {
  const code = activationCode.value.trim()
  if (!code) return
  activating.value = true
  const result = await activateProduct(code)
  if (result.success && result.data) {
    status.value = result.data
    activationCode.value = ''
    message.success('产品激活成功')
  } else {
    message.error(result.message || '激活码无效或已过期')
  }
  activating.value = false
}

onMounted(loadStatus)
</script>

<style scoped>
.product-activation-panel {
  padding-top: 4px;
}

.activation-alert {
  margin-bottom: 18px;
}

.activation-details {
  margin-bottom: 20px;
}

.activation-input {
  display: grid;
  gap: 8px;
  margin-bottom: 18px;
}

.activation-input label {
  color: #1f2937;
  font-size: 14px;
  font-weight: 600;
}

.activation-input__hint {
  color: #8a96a8;
  font-size: 12px;
}
</style>
