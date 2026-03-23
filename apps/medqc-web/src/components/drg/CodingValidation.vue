<template>
  <a-card
    title="编码校验结果"
    :bordered="false"
  >
    <a-result
      :status="validationResult.is_valid ? 'success' : 'warning'"
      :title="validationResult.is_valid ? '编码校验通过' : '编码存在问题'"
    >
      <template #subTitle>
        <span v-if="!validationResult.is_valid">
          发现 {{ validationResult.warnings.length }} 个警告，{{ validationResult.conflicts.length }} 个冲突
        </span>
      </template>
    </a-result>

    <!-- 警告列表 -->
    <div
      v-if="validationResult.warnings.length > 0"
      style="margin-top: 16px"
    >
      <h4>警告信息</h4>
      <a-list
        :data-source="validationResult.warnings"
        size="small"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #avatar>
                <a-avatar :style="{ backgroundColor: severityColor[item.severity as Severity] }">
                  <component :is="getSeverityIcon(item.severity)" />
                </a-avatar>
              </template>
              <template #title>
                <a-space>
                  <StatusTag
                    type="severity"
                    :value="item.severity"
                  />
                  <span>{{ suggestionTypeMap[item.type as keyof typeof suggestionTypeMap] }}</span>
                </a-space>
              </template>
              <template #description>
                <div>{{ item.message }}</div>
                <div
                  v-if="item.evidence"
                  style="margin-top: 4px; padding: 8px; background: #f5f5f5; border-radius: 4px; font-size: 12px"
                >
                  <strong>病历依据：</strong>{{ item.evidence }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </div>

    <!-- 冲突列表 -->
    <div
      v-if="validationResult.conflicts.length > 0"
      style="margin-top: 16px"
    >
      <h4>逻辑冲突</h4>
      <a-alert
        v-for="(conflict, index) in validationResult.conflicts"
        :key="index"
        :message="conflict"
        type="error"
        show-icon
        style="margin-bottom: 8px"
      />
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { InfoCircleOutlined, WarningOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'
import StatusTag from './StatusTag.vue'
import { severityColor, suggestionTypeMap } from '@/utils/drg'
import type { ValidationResult, Severity } from '@/types/drg'

interface Props {
  validationResult: ValidationResult
}

defineProps<Props>()

/** 获取严重程度图标 */
const getSeverityIcon = (severity: Severity) => {
  switch (severity) {
    case 'info':
      return h(InfoCircleOutlined)
    case 'warning':
      return h(WarningOutlined)
    case 'error':
      return h(CloseCircleOutlined)
    default:
      return h(InfoCircleOutlined)
  }
}
</script>
