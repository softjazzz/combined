<template>
  <a-select
    v-model:value="selectedValue"
    show-search
    :placeholder="placeholder"
    :filter-option="false"
    :not-found-content="fetching ? undefined : null"
    @search="handleSearch"
    @change="handleChange"
    style="width: 100%"
  >
    <template #notFoundContent>
      <a-spin v-if="fetching" size="small" />
      <a-empty v-else :image="Empty.PRESENTED_IMAGE_SIMPLE" />
    </template>
    <a-select-option v-for="item in searchResults" :key="item.code" :value="item.code">
      <div>
        <a-tag color="blue" size="small">{{ item.code }}</a-tag>
        <span>{{ item.name }}</span>
      </div>
    </a-select-option>
  </a-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Empty } from 'ant-design-vue'
import { drgApi } from '@/api/drg'
import type { ICDCode, CodeCategory } from '@/types/drg'

interface Props {
  value?: string
  name?: string
  category: CodeCategory
  placeholder?: string
}

interface Emits {
  (e: 'update:value', value: string): void
  (e: 'update:name', name: string): void
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '搜索编码或名称'
})

const emit = defineEmits<Emits>()

const selectedValue = ref(props.value)
const searchResults = ref<ICDCode[]>([])
const fetching = ref(false)
let searchTimeout: NodeJS.Timeout | null = null

/** 搜索ICD编码 */
const handleSearch = (keyword: string) => {
  if (!keyword) {
    searchResults.value = []
    return
  }

  // 防抖
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }

  searchTimeout = setTimeout(async () => {
    fetching.value = true
    try {
      const response = await drgApi.searchICDCodes({
        keyword,
        category: props.category,
        limit: 20
      })
      searchResults.value = response.results
    } catch (error) {
      console.error('搜索ICD编码失败:', error)
    } finally {
      fetching.value = false
    }
  }, 300)
}

/** 选择编码 */
const handleChange = (code: string) => {
  const selected = searchResults.value.find(item => item.code === code)
  if (selected) {
    emit('update:value', selected.code)
    emit('update:name', selected.name)
  }
}

watch(() => props.value, (newVal) => {
  selectedValue.value = newVal
})
</script>
