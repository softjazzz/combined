<template>
  <a-card
    title="ICD 编码推荐"
    :bordered="false"
  >
    <a-form layout="vertical">
      <a-form-item label="诊断名称">
        <a-input
          v-model:value="diagnosisName"
          placeholder="输入诊断名称，例如：急性心肌梗死"
          @press-enter="handleRecommend"
        />
      </a-form-item>
      <a-form-item label="编码类型">
        <a-radio-group v-model:value="category">
          <a-radio value="diagnosis">
            诊断
          </a-radio>
          <a-radio value="procedure">
            手术操作
          </a-radio>
        </a-radio-group>
      </a-form-item>
      <a-form-item>
        <a-button
          type="primary"
          :loading="loading"
          block
          @click="handleRecommend"
        >
          <template #icon>
            <BulbOutlined />
          </template>
          获取推荐
        </a-button>
      </a-form-item>
    </a-form>

    <a-divider />

    <div v-if="recommendations.length > 0">
      <h4>推荐结果</h4>
      <a-list
        :data-source="recommendations"
        size="small"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <template #actions>
              <a-button
                type="link"
                size="small"
                @click="handleSelect(item.code, item.name)"
              >
                采用
              </a-button>
            </template>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <a-tag color="blue">
                    {{ item.code }}
                  </a-tag>
                  <span>{{ item.name }}</span>
                </a-space>
              </template>
              <template #description>
                <a-progress
                  :percent="Math.round(item.confidence * 100)"
                  size="small"
                  :status="item.confidence > 0.8 ? 'success' : 'normal'"
                />
                <div
                  v-if="item.note"
                  style="margin-top: 4px; color: #999; font-size: 12px"
                >
                  {{ item.note }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </div>
    <a-empty
      v-else-if="searched"
      description="暂无推荐结果"
    />
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { BulbOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import type { ICDSuggestion, CodeCategory } from '@/types/drg'

interface Emits {
  (e: 'select', code: string, name: string): void
}

const emit = defineEmits<Emits>()

const diagnosisName = ref('')
const category = ref<CodeCategory>('diagnosis')
const recommendations = ref<ICDSuggestion[]>([])
const loading = ref(false)
const searched = ref(false)

/** 获取推荐 */
const handleRecommend = async () => {
  if (!diagnosisName.value.trim()) {
    message.warning('请输入诊断名称')
    return
  }

  loading.value = true
  searched.value = false
  try {
    const response = await drgApi.suggestCoding({
      diagnosis_name: diagnosisName.value,
      category: category.value
    })
    recommendations.value = response.candidates
    searched.value = true

    if (response.candidates.length === 0) {
      message.info('未找到推荐编码')
    }
  } catch (error) {
    console.error('获取推荐失败:', error)
    message.error('获取推荐失败')
  } finally {
    loading.value = false
  }
}

/** 选择推荐编码 */
const handleSelect = (code: string, name: string) => {
  emit('select', code, name)
}
</script>
