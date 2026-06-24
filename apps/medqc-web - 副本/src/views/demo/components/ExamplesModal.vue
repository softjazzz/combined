<template>
  <a-modal
    :open="visible"
    title="示例质控需求"
    width="720px"
    :footer="null"
    @cancel="handleCancel"
  >
    <a-list
      :data-source="examples"
      item-layout="vertical"
      :split="false"
    >
      <template #renderItem="{ item }">
        <a-list-item class="example-item">
          <a-list-item-meta :title="item.title" />
          <div class="example-content">
            <p class="example-text">
              {{ item.content }}
            </p>
            <a-space>
              <a-tag color="blue">
                文书：{{ item.params.documentType }}
              </a-tag>
              <a-tag color="purple">
                复杂度：{{ item.params.complexity }}
              </a-tag>
              <a-tag color="red">
                缺陷级别：{{ item.params.defectLevel }}
              </a-tag>
            </a-space>
          </div>
          <div class="example-actions">
            <a-button
              type="primary"
              @click="() => handleUseExample(item)"
            >
              使用此示例
            </a-button>
          </div>
        </a-list-item>
      </template>
    </a-list>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type RuleParams = {
  documentType: string
  defectLevel: string
  complexity: string
}

type ExampleItem = {
  title: string
  content: string
  params: RuleParams
}

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', value: ExampleItem): void
}>()

const examples: ExampleItem[] = [
  {
    title: '完整性检查 · 过敏史记录',
    content: '检查入院记录个人史是否记录患者的过敏史，包括药物过敏史和食物过敏史。如果患者无过敏史，应明确写明“无药物过敏史”“无食物过敏史”。',
    params: {
      documentType: '入院记录',
      defectLevel: '一般缺陷',
      complexity: '低复杂度'
    }
  },
  {
    title: '诊断依据 · 首次病程记录',
    content: '检查首次病程记录是否书写了初步诊断的诊断依据，需要包括主要症状、体征、重点检验/影像结果等，能够支撑诊断结论。',
    params: {
      documentType: '首次病程记录',
      defectLevel: '一般缺陷',
      complexity: '中复杂度'
    }
  },
  {
    title: '签名完整性 · 手术记录',
    content: '检查手术记录签名是否齐全。即使由助手书写，仍需有主刀医师签名确认，缺少主刀签名视为不合规。',
    params: {
      documentType: '手术记录',
      defectLevel: '严重缺陷',
      complexity: '低复杂度'
    }
  },
  {
    title: '及时性检查 · 危重病程记录',
    content: '检查危重患者的病程记录是否按要求及时书写。危重患者每天至少记录一次病程，病情变化时需实时记录。超过24小时未记录视为不合规。',
    params: {
      documentType: '病程记录',
      defectLevel: '一般缺陷',
      complexity: '中复杂度'
    }
  },
  {
    title: '一致性检查 · 出院诊断',
    content: '检查出院诊断是否与主要检验异常一致，例如存在肝功能显著异常时出院诊断应体现对应疾病，若遗漏重要异常指标需提示补充。',
    params: {
      documentType: '出院记录',
      defectLevel: '一般缺陷',
      complexity: '高复杂度'
    }
  }
]

const visible = computed(() => props.visible)

const handleUseExample = (item: ExampleItem) => {
  emit('select', item)
  emit('update:visible', false)
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<style scoped lang="less">
.example-item {
  padding: 12px 0;
  border-bottom: 1px dashed #f0f0f0;

  &:last-child {
    border-bottom: none;
  }
}

.example-content {
  margin-bottom: 12px;
}

.example-text {
  margin-bottom: 8px;
  color: #4a5568;
  line-height: 1.6;
}

.example-actions {
  text-align: right;
}
</style>
