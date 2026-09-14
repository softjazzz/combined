<template>
  <a-card
    class="rule-card"
    hoverable
  >
    <template #title>
      <div class="rule-header">
        <span class="rule-code">{{ rule.rule_code }}</span>
        <a-tag
          :color="defectLevelColor"
          class="defect-level-tag"
        >
          {{ defectLevelText }}
        </a-tag>
      </div>
    </template>

    <div class="rule-content">
      <h3 class="rule-name">
        {{ rule.name }}
      </h3>
      <p class="rule-description">
        {{ rule.description }}
      </p>

      <div class="rule-meta">
        <div class="meta-item">
          <span class="meta-label">规则类别：</span>
          <span class="meta-value">{{ rule.category }}</span>
        </div>
        <div
          v-if="rule.deduction_score"
          class="meta-item"
        >
          <span class="meta-label">扣分：</span>
          <span class="meta-value">{{ rule.deduction_score }} 分</span>
        </div>
        <div
          v-if="rule.is_veto_defect"
          class="meta-item"
        >
          <a-tag color="red">
            一票否决
          </a-tag>
        </div>
      </div>

      <div
        v-if="rule.applicable_documents?.length"
        class="rule-documents"
      >
        <span class="meta-label">适用文档：</span>
        <a-space
          :size="4"
          wrap
        >
          <a-tag
            v-for="(doc, index) in rule.applicable_documents"
            :key="index"
            color="blue"
          >
            {{ doc }}
          </a-tag>
        </a-space>
      </div>

      <div class="rule-footer">
        <a-space>
          <a-button
            type="primary"
            @click="handleEvaluate"
          >
            <PlayCircleOutlined /> 批量质控评估
          </a-button>
          <a-button
            v-if="showDetailButton"
            @click="handleDetail"
          >
            <FileTextOutlined /> 查看详情
          </a-button>
        </a-space>
        <div class="rule-status">
          <a-tag
            v-if="rule.is_enabled"
            color="success"
          >
            <CheckCircleOutlined /> 已启用
          </a-tag>
          <a-tag
            v-else
            color="default"
          >
            已禁用
          </a-tag>
        </div>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  PlayCircleOutlined,
  FileTextOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'
import type { QCRule } from '@/types/demo'

interface Props {
  rule: QCRule
  showDetailButton?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showDetailButton: false
})

const emit = defineEmits<{
  evaluate: [rule: QCRule]
  detail: [rule: QCRule]
}>()

// 缺陷等级颜色映射
const defectLevelColor = computed(() => {
  const colorMap = {
    critical: 'red',
    major: 'orange',
    minor: 'blue'
  }
  const level = props.rule.defect_level as keyof typeof colorMap | undefined
  return level ? (colorMap[level] || 'default') : 'default'
})

// 缺陷等级文本映射
const defectLevelText = computed(() => {
  const textMap = {
    critical: '严重缺陷',
    major: '重要缺陷',
    minor: '一般缺陷'
  }
  const level = props.rule.defect_level as keyof typeof textMap | undefined
  return level ? (textMap[level] || level) : ''
})

const handleEvaluate = () => {
  emit('evaluate', props.rule)
}

const handleDetail = () => {
  emit('detail', props.rule)
}
</script>

<style scoped lang="less">
.rule-card {
  height: 100%;
  transition: all 0.3s ease;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .rule-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .rule-code {
      font-size: 16px;
      font-weight: 600;
      color: #2b6cf6;
    }

    .defect-level-tag {
      font-size: 12px;
    }
  }

  .rule-content {
    .rule-name {
      font-size: 18px;
      font-weight: 600;
      color: rgba(0, 0, 0, 0.85);
      margin: 0 0 12px 0;
      line-height: 1.4;
    }

    .rule-description {
      font-size: 14px;
      color: rgba(0, 0, 0, 0.65);
      margin-bottom: 16px;
      line-height: 1.6;
    }

    .rule-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 12px;
      padding: 12px;
      background: #fafafa;
      border-radius: 4px;

      .meta-item {
        display: flex;
        align-items: center;
        gap: 4px;

        .meta-label {
          font-size: 13px;
          color: rgba(0, 0, 0, 0.45);
        }

        .meta-value {
          font-size: 13px;
          color: rgba(0, 0, 0, 0.85);
          font-weight: 500;
        }
      }
    }

    .rule-documents {
      margin-bottom: 16px;
      padding: 12px;
      background: #f0f5ff;
      border-radius: 4px;

      .meta-label {
        font-size: 13px;
        color: rgba(0, 0, 0, 0.65);
        margin-bottom: 8px;
        display: block;
      }
    }

    .rule-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 16px;
      border-top: 1px solid #f0f0f0;

      .rule-status {
        display: flex;
        align-items: center;
      }
    }
  }
}
</style>
