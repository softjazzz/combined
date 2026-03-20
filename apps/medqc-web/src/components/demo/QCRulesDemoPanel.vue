<template>
  <div class="qc-rules-demo-panel">
    <a-card title="质控规则演示" class="rules-panel">
      <template #extra>
        <a-tooltip title="规则配置">
          <SettingOutlined />
        </a-tooltip>
      </template>

      <!-- 规则库展示 -->
      <div class="rules-section">
        <!-- 四川规则标识 -->
        <a-alert
          type="info"
          show-icon
          message="质控标准"
          class="rule-source-alert"
          style="margin-bottom: 16px;"
        >
          <template #description>
            <a-space :size="8" wrap>
              <a-tag color="blue">
                <FileProtectOutlined />
                四川省标准（2023版）
              </a-tag>
              <a-tag color="green">权威规则</a-tag>
              <a-tag color="purple">LLM优化</a-tag>
            </a-space>
            <div style="margin-top: 8px; font-size: 13px;">
              基于《四川省住院病历质量评定标准（2023年版）》，包含完整的质控规则库
            </div>
          </template>
        </a-alert>

        <div class="rules-header">
          <h4>质控规则管理</h4>
          <a-typography-text type="secondary">
            在此勾选要应用的质控规则，勾选结果将用于病历分析
          </a-typography-text>
        </div>

        <div class="rules-summary">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-statistic
                title="已选规则数量"
                :value="selectedRules.length"
                suffix="条"
              />
            </a-col>
            <a-col :span="12">
              <a-statistic
                title="规则覆盖度"
                :value="selectionCoverage"
                suffix="%"
              />
            </a-col>
          </a-row>
          <a-typography-text type="secondary" class="summary-tip">
            建议勾选至少 3 条规则以保障规则覆盖范围。
          </a-typography-text>
        </div>

        <div class="rules-controls">
          <a-space>
            <a-checkbox
              :indeterminate="isIndeterminate"
              :checked="isAllChecked"
              @change="handleToggleAll"
            >
              全选当前列表
            </a-checkbox>
            <a-button size="small" @click="clearAllRules" :disabled="selectedRules.length === 0">
              清空选择
            </a-button>
          </a-space>
        </div>

        <div v-if="selectedDocuments && selectedDocuments.length > 0" class="document-filter-info" style="margin-bottom: 12px;">
          <a-alert
            type="info"
            show-icon
            :message="`已根据选中的文书类别自动筛选适用规则`"
            :description="`当前文书类别：${selectedDocTypeNames.join('、')} | 显示 ${filteredRules.length} 条适用规则`"
            banner
          />
        </div>

        <div class="rules-filter" style="margin-bottom: 16px;">
          <a-row :gutter="8">
            <a-col :span="8">
              <a-select
                v-model:value="categoryFilter"
                placeholder="按类别筛选"
                allowClear
                size="small"
                style="width: 100%;"
              >
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
              </a-select>
            </a-col>
            <a-col :span="8">
              <a-select
                v-model:value="severityFilter"
                placeholder="按严重程度筛选"
                allowClear
                size="small"
                style="width: 100%;"
              >
                <a-select-option value="high">严重</a-select-option>
                <a-select-option value="medium">重要</a-select-option>
                <a-select-option value="low">轻微</a-select-option>
              </a-select>
            </a-col>
            <a-col :span="8">
              <a-select
                v-model:value="statusFilter"
                placeholder="按状态筛选"
                allowClear
                size="small"
                style="width: 100%;"
              >
                <a-select-option value="active">启用</a-select-option>
                <a-select-option value="inactive">禁用</a-select-option>
              </a-select>
            </a-col>
          </a-row>
        </div>

        <a-list
          item-layout="horizontal"
          :data-source="filteredRules"
          :pagination="paginationConfig"
          class="rule-compact-list"
        >
          <template #renderItem="{ item }">
            <a-list-item
              :class="[
                'rule-row',
                { 'rule-selected': isRuleSelected(item), 'rule-disabled': item._disabled }
              ]"
              :actions="getItemActions(item)"
            >
              <a-list-item-meta
                :avatar="renderAvatar(item)"
                :title="renderTitle(item)"
                :description="renderDescription(item)"
              />
            </a-list-item>
          </template>
          <template #empty>
            <a-empty description="暂无匹配的规则" />
          </template>
        </a-list>
      </div>

      <!-- 测试病历信息 -->
      <div class="record-section">
        <h4>测试病历</h4>
        <div v-if="!testRecord" class="empty-record">
          <a-empty description="暂无选择的测试病历">
            <a-button type="dashed" @click="selectTestRecord">
              选择测试病历
            </a-button>
          </a-empty>
        </div>
        <div v-else class="record-info">
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item label="病历号">{{ testRecord.id }}</a-descriptions-item>
            <a-descriptions-item label="患者姓名">{{ testRecord.patient_name || testRecord.patientName }}</a-descriptions-item>
            <a-descriptions-item label="科室">{{ testRecord.department }}</a-descriptions-item>
            <a-descriptions-item label="入院日期">{{ testRecord.admission_date || testRecord.admissionDate }}</a-descriptions-item>
            <a-descriptions-item label="病历类型" :span="2">{{ testRecord.record_type || testRecord.type }}</a-descriptions-item>
          </a-descriptions>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="actions-section">
        <a-space>
          <a-button
            type="primary"
            :icon="h(PlayCircleOutlined)"
            :disabled="selectedRules.length === 0 || !testRecord"
            @click="handleStartAnalysis"
            size="large"
          >
            开始质控分析
          </a-button>
          <a-button
            :icon="h(SettingOutlined)"
            @click="handleConfigRules"
          >
            配置规则
          </a-button>
        </a-space>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import { SettingOutlined, PlayCircleOutlined, AuditOutlined, FileProtectOutlined } from '@ant-design/icons-vue'
import type { QualityControlRule } from '@/types/quality-control'
import { DOCUMENT_TYPE_TO_CATEGORY } from '@/utils/documentTypeUtils'
import { lookupRuleCategories } from '@/qc/ruleDocumentMapping'

// Props
const props = defineProps<{
  selectedRules: unknown[]
  availableRules: unknown[]
  testRecord: Record<string, unknown>
  selectedDocuments?: Array<{ id: string; title?: string; type?: string; created_at?: string }>
}>()

// Emits
const emit = defineEmits<{
  rulesUpdated: [rules: QualityControlRule[]]
  startAnalysis: []
}>()

// 响应式数据
const categoryFilter = ref<string>()
const severityFilter = ref<string>()
const statusFilter = ref<string>()
const paginationState = reactive({ current: 1, pageSize: 6 })

// 可用规则由父组件传入（来源：Supabase / 本地回退）
const availableRules = (props.availableRules || []) as any[]

const getRuleIdentity = (rule: any): string => {
  if (!rule) return ''
  return String(rule.id ?? rule.ruleCode ?? rule.name ?? '')
}

// 获取选中文书对应的"6大类"标准英文代码（用于规则匹配）
const selectedDocTypeCodes = computed<string[]>(() => {
  const docs = props.selectedDocuments || []
  const set = new Set<string>()
  docs.forEach(d => {
    const typeCode = d.type || ''
    // 将细分类(type)映射到"6大类"分类代码
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
  const docs = props.selectedDocuments || []
  const set = new Set<string>()
  docs.forEach(d => {
    const typeCode = d.type || ''
    const label = getDocumentTypeLabel(typeCode)
    if (label) set.add(label)
  })
  return Array.from(set)
})

// 文书类型中文标签映射
const DOC_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  discharge_record: '出院记录',
  operation_record: '手术相关记录',
  examination_report: '辅助检查',
  consent_form: '知情同意书',
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

function getDocumentTypeLabel(type?: string): string {
  if (!type) return ''
  return DOC_TYPE_LABELS[type] || ''
}

// 为规则标注是否适用，并将适用项排在前面
const rulesWithApplicability = computed<any[]>(() => {
  const codes = new Set(selectedDocTypeCodes.value)
  const all = availableRules
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

  const arr = all.map((r: any) => {
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
  return arr.sort((a: any, b: any) => Number(b._applicable) - Number(a._applicable))
})

// 计算属性：过滤后的规则
const filteredRules = computed(() => {
  let rules = rulesWithApplicability.value

  if (categoryFilter.value) {
    rules = rules.filter(rule => rule.category === categoryFilter.value)
  }

  if (severityFilter.value) {
    rules = rules.filter(rule => rule.severity === severityFilter.value)
  }

  if (statusFilter.value) {
    const isActive = statusFilter.value === 'active'
    rules = rules.filter(rule => rule.isActive === isActive)
  }

  return rules
})

const selectedRuleIds = computed(() => {
  const set = new Set<string>()
  ;(props.selectedRules || []).forEach((rule: any) => {
    const id = getRuleIdentity(rule)
    if (id) set.add(id)
  })
  return set
})

const selectableRulesInView = computed(() => filteredRules.value.filter(rule => !rule._disabled))

const isAllChecked = computed(() => {
  const selectable = selectableRulesInView.value
  if (selectable.length === 0) return false
  return selectable.every(rule => selectedRuleIds.value.has(getRuleIdentity(rule)))
})

const isIndeterminate = computed(() => {
  if (selectableRulesInView.value.length === 0) return false
  const hasSome = selectableRulesInView.value.some(rule => selectedRuleIds.value.has(getRuleIdentity(rule)))
  return hasSome && !isAllChecked.value
})

const handlePageChange = (page: number, pageSize?: number) => {
  paginationState.current = page
  if (pageSize && pageSize !== paginationState.pageSize) {
    paginationState.pageSize = pageSize
  }
}

const handlePageSizeChange = (_current: number, size: number) => {
  paginationState.pageSize = size
  paginationState.current = 1
}

const paginationConfig = computed(() => ({
  current: paginationState.current,
  pageSize: paginationState.pageSize,
  size: 'small',
  showSizeChanger: true,
  showQuickJumper: true,
  pageSizeOptions: ['6', '10', '20', '50'],
  onChange: handlePageChange,
  onShowSizeChange: handlePageSizeChange
}))

const selectionCoverage = computed(() => {
  return Math.round((props.selectedRules.length / Math.max(availableRules.length, 1)) * 100)
})

// 工具函数
const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'high': return 'red'
    case 'medium': return 'orange'
    case 'low': return 'blue'
    default: return 'default'
  }
}

const getSeverityText = (severity: string) => {
  switch (severity) {
    case 'high': return '高'
    case 'medium': return '中'
    case 'low': return '低'
    default: return '未知'
  }
}

// 事件处理
const handleStartAnalysis = () => {
  if (props.selectedRules.length === 0) {
    message.warning('请先选择质控规则')
    return
  }
  if (!props.testRecord) {
    message.warning('请先选择测试病历')
    return
  }
  message.success('开始质控分析...')
  // 更新父组件规则并触发开始分析
  emit('rulesUpdated', props.selectedRules)
  emit('startAnalysis')
}

const handleConfigRules = () => {
  message.info('规则配置功能开发中...')
}

const isRuleSelected = (rule: unknown) => {
  return selectedRuleIds.value.has(getRuleIdentity(rule))
}

const handleToggleRule = (rule: any, checked: boolean) => {
  const id = getRuleIdentity(rule)
  if (!id) return

  if (checked) {
    if (selectedRuleIds.value.has(id)) return
    const updated = [...props.selectedRules, rule]
    emit('rulesUpdated', updated)
  } else {
    const updated = props.selectedRules.filter(r => getRuleIdentity(r) !== id)
    emit('rulesUpdated', updated)
  }
}

const handleToggleAll = (e: any) => {
  const checked = e?.target?.checked ?? false
  const inView = selectableRulesInView.value
  if (inView.length === 0) return

  if (checked) {
    const map = new Map<string, any>()
    props.selectedRules.forEach((rule: any) => {
      const id = getRuleIdentity(rule)
      if (id) map.set(id, rule)
    })
    inView.forEach(rule => {
      const id = getRuleIdentity(rule)
      if (id) map.set(id, rule)
    })
    emit('rulesUpdated', Array.from(map.values()))
  } else {
    const idsToRemove = new Set(inView.map(rule => getRuleIdentity(rule)))
    const updated = props.selectedRules.filter(rule => !idsToRemove.has(getRuleIdentity(rule)))
    emit('rulesUpdated', updated)
  }
}

const selectTestRecord = () => {
  message.info('测试病历选择功能开发中...')
}

const clearAllRules = () => {
  emit('rulesUpdated', [])
  message.success('已清空所有规则')
}

const renderAvatar = (_item?: any) => {
  return h(
    'div',
    { class: 'rule-avatar fixed-icon' },
    h(AuditOutlined)
  )
}

const renderTitle = (item: any) => {
  return h(
    'div',
    { class: 'rule-title-row' },
    [
      h(
        'label',
        { class: 'rule-checkbox-label' },
        [
          h('input', {
            type: 'checkbox',
            checked: isRuleSelected(item),
            disabled: item._disabled,
            onChange: (e: any) => handleToggleRule(item, e.target.checked)
          }),
          h('span', { class: 'rule-title-text' }, item.name || item.ruleCode || item.id)
        ]
      ),
      h(
        'div',
        { class: 'rule-title-tags' },
        [
          h(
            'span',
            { class: ['rule-tag', `tag-${item.severity || 'medium'}`] },
            getSeverityText(item.severity || 'medium')
          ),
          h('span', { class: 'rule-tag category' }, item.category || '规则'),
          item.isActive ? h('span', { class: 'rule-tag active' }, '启用') : h('span', { class: 'rule-tag inactive' }, '禁用'),
          item._applicable ? h('span', { class: 'rule-tag applicable' }, '适用') : null
        ].filter(Boolean)
      )
    ]
  )
}

const renderDescription = (item: any) => {
  return h(
    'div',
    { class: 'rule-desc-wrapper' },
    [
      h('div', { class: 'rule-desc-meta' }, [
        h('span', { class: 'rule-meta-item' }, `权重：${item.weight ?? 1}`),
        h('span', { class: 'rule-meta-item' }, `类型：${item.ruleType || '未知'}`),
        h('span', { class: 'rule-meta-item' }, `编号：${item.ruleCode || item.id}`)
      ]),
      h('div', { class: 'rule-desc-text' }, item.description || '暂无描述')
    ]
  )
}

const getItemActions = (item: any) => {
  return [
    h(
      'span',
      {
        class: 'rule-action',
        onClick: () => handleToggleRule(item, !isRuleSelected(item))
      },
      isRuleSelected(item) ? '取消' : '选择'
    )
  ]
}

watch(filteredRules, () => {
  paginationState.current = 1
})
</script>

<style scoped lang="less">
.qc-rules-demo-panel {
  .rules-panel {
    .rules-section {
      margin-bottom: 24px;

      .rules-header {
        margin-bottom: 16px;

        h4 {
          font-weight: 600;
          margin-bottom: 4px;
          color: #333;
        }
      }

      .rules-summary {
        margin-bottom: 12px;
        padding: 14px 16px;
        background: linear-gradient(135deg, rgba(230, 244, 255, 0.92) 0%, rgba(255, 255, 255, 0.96) 100%);
        border-radius: 12px;
        box-shadow: 0 1px 6px rgba(14, 110, 209, 0.08);
        display: flex;
        flex-direction: column;
        gap: 12px;

        .summary-tip {
          font-size: 12px;
          color: var(--text-secondary);
        }
      }

      .rules-controls {
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;

        :deep(.ant-checkbox-wrapper) {
          font-weight: 500;
        }

        :deep(.ant-btn) {
          border-radius: 20px;
        }
      }

      .rules-filter {
        padding: 12px;
        background: #ffffff;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);

        :deep(.ant-select-selector) {
          border-radius: 20px;
          border-color: #d9dee5;
        }
      }

      .rule-compact-list {
        :deep(.ant-list-item) {
          padding: 12px 16px;
          transition: background-color 0.2s ease;
          align-items: center;
        }

        :deep(.rule-row.rule-selected) {
          background: rgba(24, 144, 255, 0.08);
        }

        :deep(.rule-row.rule-disabled) {
          opacity: 0.5;
        }

        :deep(.rule-row:hover) {
          background: rgba(24, 144, 255, 0.04);
        }

        :deep(.ant-list-item-meta) {
          align-items: center;
        }

        :deep(.ant-list-item-meta-avatar) {
          margin-right: 12px;
        }

        :deep(.rule-avatar) {
          width: 38px;
          height: 38px;
          border-radius: 50%;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: var(--primary-color);
          color: #fff;
          box-shadow: 0 4px 12px rgba(11, 100, 212, 0.25);
        }

        :deep(.rule-avatar.fixed-icon svg) {
          font-size: 18px;
        }

        :deep(.rule-title-row) {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        :deep(.rule-checkbox-label) {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-weight: 500;
          color: #1f1f1f;
        }

        :deep(.rule-checkbox-label input) {
          width: 14px;
          height: 14px;
          margin: 0;
        }

        :deep(.rule-title-tags) {
          display: inline-flex;
          flex-wrap: wrap;
          gap: 6px;
          font-size: 12px;
        }

        :deep(.rule-tag) {
          display: inline-flex;
          align-items: center;
          padding: 0 6px;
          height: 20px;
          border-radius: 10px;
          font-size: 12px;
          background: #f4f8ff;
          color: var(--primary-color);
        }

        :deep(.rule-tag.category) {
          background: #e6f4ff;
          color: #1d39c4;
        }

        :deep(.rule-tag.active) {
          background: #e8f5e9;
          color: #3f8600;
        }

        :deep(.rule-tag.inactive) {
          background: #fff1f0;
          color: #cf1322;
        }

        :deep(.rule-tag.applicable) {
          background: #f9f0ff;
          color: #722ed1;
        }

        :deep(.tag-high) {
          background: #fff1f0;
          color: #cf1322;
        }

        :deep(.tag-medium) {
          background: #fff7e6;
          color: #d48806;
        }

        :deep(.tag-low) {
          background: #e6f7ff;
          color: #0050b3;
        }

        :deep(.rule-desc-wrapper) {
          margin-top: 6px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        :deep(.rule-desc-meta) {
          display: inline-flex;
          flex-wrap: wrap;
          gap: 10px;
          font-size: 12px;
          color: #8c8c8c;
        }

        :deep(.rule-desc-text) {
          font-size: 13px;
          color: #595959;
          line-height: 1.5;
        }

        :deep(.rule-action) {
          cursor: pointer;
          color: var(--primary-color);
          transition: color 0.2s ease;
        }

        :deep(.rule-action:hover) {
          color: #0958d9;
        }

        @media (max-width: 768px) {
          :deep(.ant-list-item) {
            padding: 10px 12px;
          }

          :deep(.rule-title-row) {
            flex-direction: column;
            align-items: flex-start;
            gap: 6px;
          }

          :deep(.rule-title-tags) {
            width: 100%;
            justify-content: flex-start;
          }

          :deep(.rule-desc-meta) {
            gap: 8px;
          }

          :deep(.ant-list-item-action) {
            margin-left: 8px !important;
          }
        }
      }
    }

    .record-section {
      margin-bottom: 24px;

      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
        font-size: 16px;
      }

      .empty-record {
        text-align: center;
        padding: 24px;
        border: 1px dashed #d9d9d9;
        border-radius: 6px;
        background: #fafafa;
      }

      .record-info {
        border: 1px solid #f0f0f0;
        border-radius: 6px;
        overflow: hidden;
      }
    }

    .actions-section {
      text-align: center;
      padding-top: 20px;
      border-top: 1px solid #f0f0f0;
      margin-top: 24px;

  }
}
}

</style>
