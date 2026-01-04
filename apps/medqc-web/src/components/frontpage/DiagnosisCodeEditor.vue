<template>
  <div class="diagnosis-code-editor">
    <div class="diagnosis-item" v-for="(diag, index) in diagnoses" :key="index">
      <div class="diagnosis-row">
        <div class="diagnosis-info">
          <a-tag v-if="index === 0" color="blue">主诊断</a-tag>
          <a-tag v-else color="default">其他诊断</a-tag>
          <span class="diagnosis-name">{{ diag.name }}</span>
        </div>
        
        <!-- ICD 编码选择 -->
        <div class="icd-code-section">
          <template v-if="diag.suggestions && diag.suggestions.length > 0">
            <a-select
              v-model:value="diag.selectedCode"
              style="width: 280px"
              placeholder="选择 ICD 编码"
              @change="(val) => handleCodeChange(index, val)"
            >
              <a-select-option 
                v-for="suggestion in diag.suggestions" 
                :key="suggestion.code" 
                :value="suggestion.code"
              >
                <div class="suggestion-option">
                  <a-tag color="green" size="small">{{ suggestion.code }}</a-tag>
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
            :category="'diagnosis'"
            :value="diag.selectedCode"
            :placeholder="'搜索 ICD-10 编码'"
            @update:value="(val) => handleCodeChange(index, val)"
          />
        </div>
      </div>
      
      <!-- 显示当前选中的编码 -->
      <div v-if="diag.selectedCode" class="selected-code">
        <CheckCircleOutlined class="text-green-500" />
        <span>已选编码: <a-tag color="blue">{{ diag.selectedCode }}</a-tag></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { CheckCircleOutlined } from '@ant-design/icons-vue'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'

interface ICDSuggestion {
  code: string
  name: string
  confidence?: number
}

interface DiagnosisItem {
  name: string
  selectedCode?: string
  suggestions?: ICDSuggestion[]
}

interface Props {
  mainDiagnosis?: string
  mainDiagnosisCode?: string
  mainDiagnosisSuggestions?: ICDSuggestion[]
  otherDiagnoses?: string[]
  otherDiagnosesCodes?: (string | null)[]
  otherDiagnosesSuggestions?: { diagnosis: string; suggestions: ICDSuggestion[] }[]
}

interface Emits {
  (e: 'update:mainDiagnosisCode', code: string): void
  (e: 'update:otherDiagnosesCodes', codes: (string | null)[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 构建诊断列表
const diagnoses = computed<DiagnosisItem[]>(() => {
  const result: DiagnosisItem[] = []
  
  // 主诊断
  if (props.mainDiagnosis) {
    result.push({
      name: props.mainDiagnosis,
      selectedCode: props.mainDiagnosisCode,
      suggestions: props.mainDiagnosisSuggestions || []
    })
  }
  
  // 其他诊断
  if (props.otherDiagnoses) {
    props.otherDiagnoses.forEach((diag, idx) => {
      const suggestionItem = props.otherDiagnosesSuggestions?.find(s => s.diagnosis === diag)
      result.push({
        name: diag,
        selectedCode: props.otherDiagnosesCodes?.[idx] || undefined,
        suggestions: suggestionItem?.suggestions || []
      })
    })
  }
  
  return result
})

// 处理编码变更
const handleCodeChange = (index: number, code: string) => {
  if (index === 0) {
    emit('update:mainDiagnosisCode', code)
  } else {
    const newCodes = [...(props.otherDiagnosesCodes || [])]
    newCodes[index - 1] = code
    emit('update:otherDiagnosesCodes', newCodes)
  }
}
</script>

<style scoped>
.diagnosis-code-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.diagnosis-item {
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.diagnosis-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.diagnosis-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.diagnosis-name {
  font-weight: 500;
  color: #333;
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
