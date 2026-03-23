<template>
  <div class="procedure-code-editor">
    <div
      v-if="procedureName"
      class="procedure-item"
    >
      <div class="procedure-row">
        <div class="procedure-info">
          <a-tag color="purple">
            主手术
          </a-tag>
          <span class="procedure-name">{{ procedureName }}</span>
          <span
            v-if="procedureDate"
            class="procedure-date"
          >{{ procedureDate }}</span>
        </div>
        
        <!-- ICD-9-CM-3 编码选择 -->
        <div class="icd-code-section">
          <template v-if="suggestions && suggestions.length > 0">
            <a-select
              v-model:value="selectedCode"
              style="width: 300px"
              placeholder="选择手术编码"
              @change="handleCodeChange"
            >
              <a-select-option 
                v-for="suggestion in suggestions" 
                :key="suggestion.code" 
                :value="suggestion.code"
              >
                <div class="suggestion-option">
                  <a-tag
                    color="purple"
                    size="small"
                  >
                    {{ suggestion.code }}
                  </a-tag>
                  <span class="suggestion-name">{{ suggestion.name }}</span>
                  <a-tag 
                    v-if="suggestion.confidence" 
                    :color="suggestion.confidence > 0.9 ? 'green' : suggestion.confidence > 0.7 ? 'orange' : 'default'"
                    size="small"
                  >
                    {{ Math.round(suggestion.confidence * 100) }}%
                  </a-tag>
                </div>
              </a-select-option>
            </a-select>
          </template>
          
          <!-- 手动搜索 -->
          <ICDCodeSearch
            v-else
            :category="'procedure'"
            :value="selectedCode"
            :placeholder="'搜索 ICD-9-CM-3 编码'"
            @update:value="handleCodeChange"
          />
        </div>
      </div>
      
      <!-- 显示当前选中的编码 -->
      <div
        v-if="selectedCode"
        class="selected-code"
      >
        <CheckCircleOutlined class="text-green-500" />
        <span>已选编码: <a-tag color="purple">{{ selectedCode }}</a-tag></span>
      </div>
    </div>
    
    <a-empty
      v-else
      description="暂无手术记录"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Empty } from 'ant-design-vue'
import { CheckCircleOutlined } from '@ant-design/icons-vue'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'

interface ICDSuggestion {
  code: string
  name: string
  confidence?: number
}

interface Props {
  procedureName?: string
  procedureDate?: string
  procedureCode?: string
  suggestions?: ICDSuggestion[]
}

interface Emits {
  (e: 'update:procedureCode', code: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const selectedCode = ref(props.procedureCode)

watch(() => props.procedureCode, (newVal) => {
  selectedCode.value = newVal
})

const handleCodeChange = (code: string) => {
  selectedCode.value = code
  emit('update:procedureCode', code)
}
</script>

<style scoped>
.procedure-code-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.procedure-item {
  padding: 12px;
  background: #f9f0ff;
  border-radius: 6px;
  border: 1px solid #d3adf7;
}

.procedure-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.procedure-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.procedure-name {
  font-weight: 500;
  color: #333;
}

.procedure-date {
  color: #666;
  font-size: 12px;
}

.icd-code-section {
  flex-shrink: 0;
}

.suggestion-option {
  display: flex;
  align-items: center;
  gap: 6px;
}

.suggestion-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}

.selected-code {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #666;
}
</style>
