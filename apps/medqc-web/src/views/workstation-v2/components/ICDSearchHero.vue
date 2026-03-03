<template>
  <div class="icd-hero">
    <!-- 版本切换 + 类型切换 -->
    <div class="hero-toggles">
      <a-segmented
        v-model:value="localVersion"
        :options="versionTabs"
        size="large"
        @change="$emit('update:codeVersion', $event)"
      />
      <a-segmented
        v-model:value="localType"
        :options="codeTypeTabs"
        size="large"
        @change="$emit('update:codeType', $event)"
      />
    </div>

    <!-- 大搜索框 -->
    <div class="hero-search">
      <a-input
        v-model:value="localQuery"
        :placeholder="localType === 'icd10' ? '搜索诊断名称或 ICD-10 编码…' : '搜索手术名称或 ICD-9 编码…'"
        allow-clear
        size="large"
        @pressEnter="$emit('search', localQuery)"
        @change="onQueryChange"
      >
        <template #prefix>
          <SearchOutlined class="search-icon" />
        </template>
        <template #suffix>
          <span v-if="localQuery.length > 0" class="search-hint">
            按 Enter 搜索
          </span>
        </template>
      </a-input>
    </div>

    <!-- 统计信息 -->
    <div class="hero-stats">
      <div class="stat-item">
        <span class="stat-dot stat-dot--blue"></span>
        <span class="stat-label">ICD-10 诊断</span>
        <span class="stat-value">{{ stats.icd10Count?.toLocaleString() || '—' }} 条</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-dot stat-dot--green"></span>
        <span class="stat-label">ICD-9-CM-3 手术</span>
        <span class="stat-value">{{ stats.icd9Count?.toLocaleString() || '—' }} 条</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { SearchOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  codeVersion: string
  codeType: string
  searchQuery: string
  stats: { icd10Count?: number; icd9Count?: number }
}>()

const emit = defineEmits<{
  'update:codeVersion': [value: string]
  'update:codeType': [value: string]
  'update:searchQuery': [value: string]
  search: [value: string]
}>()

const localVersion = ref(props.codeVersion)
const localType = ref(props.codeType)
const localQuery = ref(props.searchQuery)

const versionTabs = [
  { label: '🏥 临床版', value: 'clinical' },
  { label: '🏦 医保版', value: 'insurance' },
]

const codeTypeTabs = [
  { label: '诊断搜索 (ICD-10)', value: 'icd10' },
  { label: '手术搜索 (ICD-9)', value: 'icd9cm3' },
]

// 父组件 → 子组件同步
watch(() => props.codeVersion, (v) => { localVersion.value = v })
watch(() => props.codeType, (v) => { localType.value = v })
watch(() => props.searchQuery, (v) => { localQuery.value = v })

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function onQueryChange() {
  emit('update:searchQuery', localQuery.value)
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (localQuery.value.length >= 2) {
      emit('search', localQuery.value)
    }
  }, 300)
}
</script>

<style scoped>
.icd-hero {
  padding: 24px 32px 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f1fd 50%, #f5f0ff 100%);
  border-bottom: 1px solid rgba(0, 102, 204, 0.08);
}

.hero-toggles {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.hero-toggles :deep(.ant-segmented) {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 10px;
  padding: 3px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.hero-toggles :deep(.ant-segmented-item-selected) {
  border-radius: 8px !important;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.15);
}

.hero-search {
  max-width: 720px;
  margin: 0 auto 16px;
}

.hero-search :deep(.ant-input-affix-wrapper) {
  background: #fff;
  border: 1.5px solid rgba(0, 102, 204, 0.15);
  border-radius: 12px;
  padding: 10px 16px;
  font-size: 15px;
  box-shadow: 0 4px 16px rgba(0, 102, 204, 0.06);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.hero-search :deep(.ant-input-affix-wrapper:hover),
.hero-search :deep(.ant-input-affix-wrapper-focused) {
  border-color: #0066CC;
  box-shadow: 0 4px 20px rgba(0, 102, 204, 0.12);
}

.search-icon {
  font-size: 18px;
  color: #0066CC;
  margin-right: 4px;
}

.search-hint {
  font-size: 12px;
  color: #bfbfbf;
  white-space: nowrap;
}

.hero-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.stat-dot--blue { background: #0066CC; }
.stat-dot--green { background: #00A651; }

.stat-label {
  font-size: 13px;
  color: #666;
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  font-variant-numeric: tabular-nums;
}

.stat-divider {
  width: 1px;
  height: 16px;
  background: #d9d9d9;
}
</style>
