<template>
  <a-modal
    v-model:visible="innerVisible"
    :title="modalTitle"
    width="960px"
    @cancel="handleCancel"
  >
    <!-- 步骤指示器 -->
    <a-steps :current="currentStep - 1" style="margin-bottom: 12px">
      <a-step title="选择病历与文书" />
      <a-step title="选择质控规则" />
      <a-step title="确认" />
    </a-steps>

    <!-- 第一步：病历 + 文书 -->
    <div v-if="currentStep === 1" class="picker-wrap">
      <a-row :gutter="16">
        <a-col :span="11">
          <a-card size="small" title="病历列表" :extra="recordCountExtra">
            <a-input-search v-model:value="recordKeyword" placeholder="按患者/科室/住院号搜索" allow-clear @search="onRecordSearch" style="margin-bottom: 8px" />
            <a-list :data-source="filteredRecords" :row-key="r => r.id" :loading="isLoadingRecords" item-layout="horizontal" class="scroll-list">
              <template #renderItem="{ item }">
                <a-list-item :class="['record-item', { active: selectedRecord && selectedRecord.id === item.id }]" @click="selectRecord(item)">
                  <a-list-item-meta>
                    <template #title>
                      <div class="record-title">
                        <strong>{{ item.patient_name }}</strong>
                        <a-tag size="small">{{ item.department }}</a-tag>
                      </div>
                    </template>
                    <template #description>
                      <div class="record-desc">
                        <span>入院：{{ item.admission_date || '未知' }}</span>
                        <span v-if="item.qc_score">得分：{{ item.qc_score }}</span>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </a-col>

        <a-col :span="13">
          <a-card size="small" title="文书列表" :extra="docCountExtra">
            <a-input-search v-model:value="docKeyword" placeholder="按标题/类型筛选" allow-clear style="margin-bottom: 8px" />
            <div class="doc-toolbar">
              <a-space align="center">
                <span>选择模式：</span>
                <a-switch v-model:checked="isMulti" checked-children="多选" un-checked-children="单选" />
                <a-badge :count="selectedCount" :overflow-count="999">
                  <a-tag color="blue">已选</a-tag>
                </a-badge>
                <a-button v-if="isMulti" size="small" @click="selectAllDocs" :disabled="filteredDocuments.length===0">全选</a-button>
                <a-button v-if="isMulti" size="small" @click="clearAllDocs" :disabled="selectedCount===0">清空</a-button>
              </a-space>
            </div>

            <a-empty v-if="!selectedRecord && !isLoadingDocs" description="请先在左侧选择一个病历" />
            <a-skeleton v-else-if="isLoadingDocs" :active="true" :paragraph="{ rows: 4 }" />
            <a-list v-else :data-source="filteredDocuments" :row-key="d => d.id" item-layout="horizontal" class="scroll-list">
              <template #renderItem="{ item }">
                <a-list-item :class="['doc-item', { active: isSelected(item) }]" @click="toggleDoc(item)">
                  <a-list-item-meta>
                    <template #title>
                      <div class="doc-title">
                        <template v-if="!isMulti">
                          <a-radio :checked="isSelected(item)" style="margin-right: 8px" />
                        </template>
                        <template v-else>
                          <a-checkbox :checked="isSelected(item)" style="margin-right: 8px" @click.stop="toggleDoc(item)" />
                        </template>
                        <strong>{{ item.title }}</strong>
                        <a-tag
                          v-if="docTypeLabel(getDocTypeCode(item))"
                          size="small"
                          :class="['doc-type-tag', { edited: isDocTypeEdited(item) }]"
                          color="blue"
                        >
                          {{ docTypeLabel(getDocTypeCode(item)) }}
                        </a-tag>
                        <a-select
                          class="type-editor"
                          size="small"
                          v-model:value="editedTypes[item.id]"
                          placeholder="调整类型"
                          style="width: 180px"
                          :show-search="true"
                          :dropdown-match-select-width="false"
                          :get-popup-container="getPopupContainer"
                          @click.stop
                          @mousedown.stop
                        >
                          <a-select-option v-for="opt in DOC_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                          </a-select-option>
                        </a-select>
                      </div>
                    </template>
                    <template #description>
                      <div class="doc-desc">
                        <span>创建时间：{{ item.created_at || '未知' }}</span>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 第二步：选择质控规则 -->
    <div v-else-if="currentStep === 2" class="rules-wrap">
      <a-card size="small" :title="`质控规则（已选 ${selectedRulesLocal.length} 条）`">
        <div class="flex items-center gap-2" style="margin-bottom: 8px">
          <a-input-search v-model:value="ruleKeyword" placeholder="按名称/类别筛选" allow-clear style="flex: 1" />
          <a-switch v-model:checked="onlyShowApplicable" checked-children="只看适用" un-checked-children="全部" />
        </div>
        <a-list :data-source="filteredRules" :row-key="r => r.id" item-layout="horizontal" class="scroll-list">
          <template #renderItem="{ item }">
            <a-list-item :class="['rule-item', { disabled: item._disabled }]" @click="!item._disabled && toggleRule(item)">
              <template #actions>
                <a-checkbox
                  :checked="isRuleChecked(item)"
                  :disabled="item._disabled"
                  @click.stop="toggleRule(item)"
                />
              </template>
              <a-list-item-meta :title="item.name || item.ruleCode || item.id" :description="item.description || '暂无描述'">
                <template #avatar>
                  <a-avatar :style="{ backgroundColor: getSeverityColor(item.severity || 'medium') }">
                    {{ getSeverityText(item.severity || 'medium').charAt(0) }}
                  </a-avatar>
                </template>
              </a-list-item-meta>
              <div>
                <a-space>
                  <a-tag size="small" :color="getSeverityColor(item.severity || 'medium')">{{ getSeverityText(item.severity || 'medium') }}</a-tag>
                  <a-tag size="small" color="blue">{{ item.category || '规则' }}</a-tag>
                  <a-tag v-if="item._disabled" size="small">不适用</a-tag>
                </a-space>
              </div>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </div>

    <!-- 第三步：确认 -->
    <div v-else class="confirm-wrap">
      <a-result status="success" title="请确认选择">
        <template #subTitle>
          病历：{{ selectedRecord?.patient_name || '未选择' }} · 文书：{{ selectedCount }} 份 · 规则：{{ selectedRulesLocal.length }} 条
        </template>
      </a-result>
    </div>

    <!-- 自定义底部导航按钮 -->
    <template #footer>
      <div class="footer-actions">
        <a-space>
          <a-button @click="handleCancel">取消</a-button>
        </a-space>
        <a-space>
          <a-button v-if="currentStep > 1" @click="prevStep">上一步</a-button>
          <a-button v-if="currentStep < 3" type="primary" :disabled="nextDisabled" @click="nextStep">下一步</a-button>
          <a-button v-else type="primary" :disabled="!canFinish" @click="finish">开始质控</a-button>
        </a-space>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useQCDemoStore } from '@/stores/qcDemo'
import { DemoDataService } from '@/services/demoDataService'
import { DOCUMENT_TYPE_TO_CATEGORY } from '@/utils/documentTypeUtils'
import { lookupRuleCategories } from '@/qc/ruleDocumentMapping'

type DocInfo = { id: string; title?: string; type?: string; created_at?: string }

const props = defineProps<{
  modelValue?: boolean
  selectionMode?: 'single' | 'multiple'
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'picked', payload: { record: unknown; document: DocInfo | null; documents: DocInfo[] }): void
}>()

const innerVisible = computed({
  get: () => props.modelValue ?? false,
  set: (v: boolean) => emit('update:modelValue', v)
})

const demoStore = useQCDemoStore()
const dataService = DemoDataService.getInstance()


// ===== 向导步骤状态 =====
const currentStep = ref<1 | 2 | 3>(1)
const modalTitle = computed(() => {
  return currentStep.value === 1
    ? '选择测试对象（病历 + 文书）'
    : currentStep.value === 2
      ? '选择质控规则'
      : '确认选择'
})

// 规则选择（第二步）
const ruleKeyword = ref('')
const selectedRulesLocal = ref<any[]>([])

// 四川省规则数据源（前端直接从后端接口获取）
const sichuanRules = ref<any[]>([])
const isLoadingSichuanRules = ref(false)

function mapDefectLevelToSeverity(level?: string) {
  const s = (level || '').toLowerCase()
  if (!s) return 'medium'
  if (s.includes('critical') || level?.includes('否决') || level?.includes('严重')) return 'high'
  if (s.includes('major') || level?.includes('一般')) return 'medium'
  if (s.includes('minor') || level?.includes('轻微')) return 'low'
  return 'medium'
}

async function loadSichuanRules() {
  if (isLoadingSichuanRules.value || sichuanRules.value.length > 0) return
  isLoadingSichuanRules.value = true
  try {
    const base = (import.meta as any).env?.VITE_API_BASE_URL || ''
    // 优先使用"规则管理页"同源接口 /api/v1/semantic-rules，字段与管理页一致，包含 applicable_documents
    const candidates = [
      `${base}/api/v1/semantic-rules`,
      '/api/v1/semantic-rules',
      `${base}/api/v1/qc/sichuan/rules`,
      '/api/v1/qc/sichuan/rules',
      `${location.protocol}//${location.hostname}:8001/api/v1/semantic-rules`,
      `${location.protocol}//${location.hostname}:8001/api/v1/qc/sichuan/rules`
    ]

    let data: unknown = null
    for (const url of candidates) {
      try {
        const resp = await fetch(url, { cache: 'no-store' })
        if (resp.ok) {
          data = await resp.json()
          break
        }
      } catch (_) {
        // 尝试下一个候选地址
      }
    }

    if (data) {
      const raw = Array.isArray(data) ? data : (data.rules || [])
      sichuanRules.value = raw.map((r: unknown) => ({
        id: r.rule_id || r.id || r.ruleCode || r.code,
        name: r.name || r.rule_name || '未命名规则',
        description: r.description || r.desc || '',
        category: r.category || r.rule_category || '规则',
        defect_level: r.defect_level || r.severity || '',
        severity: mapDefectLevelToSeverity(r.defect_level || r.severity),
        applicable_documents: r.applicable_documents || r.document_types || []
      }))
    } else {
      console.error('加载四川省规则失败：所有候选地址均不可用')
    }
  } catch (e) {
    console.error('加载四川省规则异常', e)
  } finally {
    isLoadingSichuanRules.value = false
  }
}

// 获取选中文书对应的“6大类”标准英文代码（用于规则匹配）
const selectedDocTypeCodes = computed<string[]>(() => {
  const docs = isMulti.value ? selectedDocuments.value : (selectedDocument.value ? [selectedDocument.value] : [])
  const set = new Set<string>()
  docs.forEach(d => {
    const typeCode = getDocTypeCode(d)
    // 将细分类(type)映射到“6大类”分类代码
    const cat = (DOCUMENT_TYPE_TO_CATEGORY as any)[typeCode]
    let mapped = cat as string | undefined
    if (!mapped) {
      const s = (typeCode || '').toLowerCase()
      if (s.includes('admission')) mapped = 'admission_record'
      else if (s.includes('discharge')) mapped = 'discharge_record'
      else if (s.includes('operation') || s.includes('surgery') || s.includes('preoperative') || s.includes('anesthesia')) mapped = 'operation_record'
      else if (s.includes('imaging') || s.includes('lab') || s.includes('examination') || s.includes('report')) mapped = 'examination_report'
      else mapped = 'progress_note'
    }
    if (mapped) set.add(mapped)
  })
  return Array.from(set)
})

// 获取选中文书的中文名称（用于显示）
const selectedDocTypeNames = computed<string[]>(() => {
  const docs = isMulti.value ? selectedDocuments.value : (selectedDocument.value ? [selectedDocument.value] : [])
  const set = new Set<string>()
  docs.forEach(d => {
    const label = docTypeLabel(getDocTypeCode(d))
    if (label) set.add(label)
  })
  return Array.from(set)
})

// 为规则标注是否适用，并将适用项排在前面
const rulesWithApplicability = computed<any[]>(() => {
  const codes = new Set(selectedDocTypeCodes.value)
  const all = sichuanRules.value
  if (codes.size === 0) return all.map(r => ({ ...r, _applicable: true, _disabled: false }))

  const labelToCode: Record<string, string> = {
    '入院记录': 'admission_record',
    '病程记录': 'progress_note',
    '出院记录': 'discharge_record',
    '手术相关记录': 'operation_record',
    '手术记录': 'operation_record',
    '辅助检查': 'examination_report',
    '检查记录': 'examination_report',
    '知情同意书': 'consent_form'
  }
  const normalize = (d: string): string | undefined => {
    if (!d) return undefined
    const s = String(d).trim()
    if (['admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'].includes(s)) return s
    return labelToCode[s]
  }

  const arr = all.map((r: unknown) => {
    // 1) 先尝试从映射表/后端字段取得标准类别集合
    const mapped = lookupRuleCategories(r)
    const raw: string[] = mapped.length > 0 ? mapped : (r.applicable_documents || [])
    const norm = raw.map(normalize).filter((x): x is string => !!x)
    let applicable = false
    if (codes.size === 1) {
      const [only] = Array.from(codes)
      // 修正：规则的文书类别列表中包含选中的类别即为适用
      applicable = norm.length > 0 && norm.some(d => codes.has(d))
      // 额外保护：若只选了入院记录，名称/描述命中手术相关关键词则不视为适用
      if (only === 'admission_record') {
        const text = `${r.name || ''} ${r.description || ''}`
        if (/手术|术前|术后|术中|麻醉|植入|出入量|出院|死亡/.test(text)) {
          applicable = false
        }
      }
    } else {
      applicable = norm.some(d => codes.has(d))
    }
    return { ...r, _applicable: applicable, _disabled: !applicable }
  })
  return arr.sort((a: unknown, b: unknown) => Number(b._applicable) - Number(a._applicable))
})

const onlyShowApplicable = ref(true)
const availableRules = computed<any[]>(() => {
  const list = rulesWithApplicability.value
  return onlyShowApplicable.value ? list.filter(r => r._applicable) : list
})

const filteredRules = computed<any[]>(() => {
  const kw = ruleKeyword.value.trim().toLowerCase()
  let base = availableRules.value
  if (!kw) return base
  return base.filter((r: unknown) =>
    [r.name, r.category, r.description, r.ruleCode, r.id]
      .filter(Boolean)
      .some((f: unknown) => String(f).toLowerCase().includes(kw))
  )
})

const isRuleChecked = (rule: unknown) => selectedRulesLocal.value.some(r => r.id === rule.id)
const toggleRule = (rule: unknown) => {
  if (rule._disabled) return
  const idx = selectedRulesLocal.value.findIndex(r => r.id === rule.id)
  if (idx >= 0) selectedRulesLocal.value.splice(idx, 1)
  else selectedRulesLocal.value.push(rule)
}


// 进入第2步时加载四川省规则
watch(currentStep, (s) => {
  if (s === 2) loadSichuanRules()
})

// 严重程度显示
function getSeverityColor(sev: string) {
  switch (sev) {
    case 'high':
    case 'critical':
      return 'red'
    case 'medium':
      return 'orange'
    case 'low':
      return 'blue'
    default:
      return 'default'
  }
}
function getSeverityText(sev: string) {
  switch (sev) {
    case 'high':
    case 'critical':
      return '高'
    case 'medium':
      return '中'
    case 'low':
      return '低'
    default:
      return '未知'
  }
}

// 导航控制
const nextDisabled = computed(() => {
  if (currentStep.value === 1) return !(selectedRecord.value && selectedCount.value > 0)
  if (currentStep.value === 2) return selectedRulesLocal.value.length === 0
  return false
})
const canFinish = computed(() =>
  !!selectedRecord.value && selectedCount.value > 0 && selectedRulesLocal.value.length > 0
)
const nextStep = () => { if (currentStep.value < 3 && !nextDisabled.value) currentStep.value++ }
const prevStep = () => { if (currentStep.value > 1) currentStep.value-- }
const finish = () => {
  if (!canFinish.value) return
  // 回填至 store
  demoStore.selectedRules = selectedRulesLocal.value as any
  const docs = isMulti.value
    ? selectedDocuments.value
    : (selectedDocument.value ? [selectedDocument.value] : [])
  emit('picked', { record: selectedRecord.value!, document: docs[0] || null, documents: docs })
  innerVisible.value = false
}

const isLoadingRecords = computed(() => demoStore.isLoadingData)
const isLoadingDocs = ref(false)

const recordKeyword = ref('')
const docKeyword = ref('')

const selectedRecord = ref<any | null>(null)
const isMulti = ref(props.selectionMode === 'multiple')
const selectedDocument = ref<DocInfo | null>(null)
const selectedDocuments = ref<DocInfo[]>([])

const selectedCount = computed(() => (isMulti.value ? selectedDocuments.value.length : (selectedDocument.value ? 1 : 0)))

const documents = ref<Array<DocInfo>>([])


// 文书类型中文标签映射（未知类型不显示）——使用更精细的小类命名
const DOC_TYPE_LABELS: Record<string, string> = {
  // 6个标准文书分类（大类）
  admission_record: '入院记录',
  progress_note: '病程记录',
  discharge_record: '出院记录',
  operation_record: '手术相关记录',
  examination_report: '辅助检查',
  consent_form: '知情同意书',

  // 细分小类
  first_progress_note: '首次病程记录',
  daily_progress_note: '日常病程记录',
  attending_first_progress: '查房记录',
  attending_progress: '查房记录',
  consultation_record: '会诊记录',
  handover_record: '接班记录',
  stage_summary: '阶段小结',
  preoperative_summary: '术前小结',
  preoperative_discussion: '术前讨论',
  preoperative_checklist: '术前核查',
  admission_note: '入院记录',
  discharge_summary: '出院小结',
  anesthesia_record: '麻醉记录',
  nursing_record: '护理记录'
}
function docTypeLabel(t?: string): string {
  if (!t) return ''
  return DOC_TYPE_LABELS[t] || ''
}

const filteredRecords = computed(() => {
  const kw = recordKeyword.value.trim()
  if (!kw) return demoStore.availableRecords


  return demoStore.availableRecords.filter(r =>
    [r.patient_name, r.department, r.id, r.record_type]
      .filter(Boolean)
      .some((f: unknown) => String(f).toLowerCase().includes(kw.toLowerCase()))
  )
})

const filteredDocuments = computed(() => {
  const kw = docKeyword.value.trim()
  if (!kw) return documents.value
  return documents.value.filter(d =>
    [d.title, docTypeLabel(getDocTypeCode(d))]
      .filter(Boolean)
      .some(f => String(f).toLowerCase().includes(kw.toLowerCase()))
  )
})

// 手动类型调整：本地状态 + 工具方法（组件级作用域）
const editedTypes = ref<Record<string, string>>({})
const DOC_TYPE_OPTIONS = Object.entries(DOC_TYPE_LABELS).map(([value, label]) => ({ value, label }))
function getDocTypeCode(d: DocInfo): string {
  return editedTypes.value[d.id] ?? d.type ?? ''
}
function isDocTypeEdited(d: DocInfo): boolean {
  const code = editedTypes.value[d.id]
  return !!code && code !== (d.type || '')
}


const recordCountExtra = computed(() => `共 ${demoStore.availableRecords.length} 条`)
// antd 选择器弹层挂载容器（避免定位问题）
const getPopupContainer = () => document.body

const docCountExtra = computed(() => selectedRecord.value ? `共 ${documents.value.length} 份 | 已选 ${selectedCount.value}` : '')

async function loadDocuments(recordId: string) {
  isLoadingDocs.value = true
  try {
    editedTypes.value = {}
    documents.value = await dataService.getDocumentsForRecord(recordId)
  } finally {
    isLoadingDocs.value = false
  }
}

function selectRecord(r: unknown) {
  selectedRecord.value = r
  selectedDocument.value = null
  selectedDocuments.value = []
  loadDocuments(r.id)
}

function isSelected(d: DocInfo) {
  return isMulti.value
    ? selectedDocuments.value.some(x => x.id === d.id)
    : (selectedDocument.value?.id === d.id)
}

function toggleDoc(d: DocInfo) {
  if (!isMulti.value) {
    selectedDocument.value = d
  } else {
    const idx = selectedDocuments.value.findIndex(x => x.id === d.id)
    if (idx >= 0) selectedDocuments.value.splice(idx, 1)
    else selectedDocuments.value.push(d)
  }
}

function selectAllDocs() {
  selectedDocuments.value = [...filteredDocuments.value]
}
function clearAllDocs() {
  selectedDocuments.value = []
}

function onRecordSearch() {
  // no-op; computed handles filtering
}

function handleOk() {
  if (selectedRecord.value && selectedCount.value > 0) {
    const docs = isMulti.value
      ? selectedDocuments.value
      : (selectedDocument.value ? [selectedDocument.value] : [])
    emit('picked', { record: selectedRecord.value, document: docs[0] || null, documents: docs })
    innerVisible.value = false
  }
}

function handleCancel() {
  innerVisible.value = false
}

watch(innerVisible, (v) => {
  if (v) {
    // 重置到第一步
    currentStep.value = 1
    // 初始化关键字
    recordKeyword.value = ''
    docKeyword.value = ''
    ruleKeyword.value = ''
    // 初始化已选病历与文书
    selectedRecord.value = demoStore.testRecord || null
    const storeDoc: unknown = demoStore.selectedDocument
    if (Array.isArray(storeDoc)) {
      isMulti.value = true
      selectedDocuments.value = storeDoc
      selectedDocument.value = storeDoc[0] || null
    } else {
      isMulti.value = props.selectionMode === 'multiple' ? true : false
      selectedDocument.value = storeDoc || null
      selectedDocuments.value = storeDoc ? [storeDoc] : []
    }
    // 初始化规则选择：为避免上次会话或默认规则干扰，此处不预填充，交由用户本次选择
    selectedRulesLocal.value = []

    if (selectedRecord.value) loadDocuments(selectedRecord.value.id)
  }
})

onMounted(async () => {
  // 打开对话框即刻准备数据：若列表为空，触发一次加载；并在 1s 后仍为空则强制刷新一次
  try {
    if (demoStore.availableRecords.length === 0) {
      await demoStore.loadTestData()
    }
    setTimeout(() => {
      if (demoStore.availableRecords.length === 0) {
        demoStore.refreshData()
      }
    }, 1000)
  } catch (_) {
    // 忽略
  }
})
</script>

<style scoped lang="less">
.picker-wrap {
  .scroll-list {
    max-height: 420px;
    overflow: auto;
  }
  .doc-toolbar {
    margin-bottom: 8px;
  }
  .record-item,
  .doc-item {
    cursor: pointer;
  }
  .record-item.active,
  .doc-item.active {
    background: #f0f5ff;
  }
  .type-editor { margin-left: 8px; }
  .doc-type-tag.edited { border-color: #722ed1; color: #722ed1; }

  .record-title,.doc-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .record-desc,.doc-desc {
    display: flex;
    gap: 12px;
    color: #888;
    font-size: 12px;
  }
}

.rules-wrap {
  .scroll-list {
    max-height: 420px;
    overflow: auto;
  }
  .rule-item.disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .rule-item.disabled :deep(.ant-list-item-meta-title),
  .rule-item.disabled :deep(.ant-list-item-meta-description) {
    color: #999;
  }
}
.footer-actions {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

</style>
