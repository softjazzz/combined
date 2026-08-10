import type {
  EditableMedicalRecordDocument,
  ManualSampleValidationMode,
  ManualSampleValidationRuleSet,
} from './types'
import type {
  SichuanBatchJob,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'

export const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
export const FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY = 'sc_content_full_v1'
export const SC_SAMPLE_RULE_SET_KEY = 'sc_sample_running_v1'
export const PROGRAMMATIC_RULE_SET_KEY = 'sample_programmatic_gate_v1'
export const LEGACY_CUSTOMER_RULE_SET_KEY = 'customer_luxian_full_v1'
export const SAMPLE_RULE_SET_RUN_TIMEOUT_MS = 90000
export const RUN_DUPLICATE_GUARD_MS = 120000
export const CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY = 'medqc_customer_sample_validation_guide_seen_v1'
export type LuxianRuleOption = {
  ruleId: string
  name: string
  description: string
  requiredDocumentsLabel: string
}

export type LuxianRuleFamilyView = {
  key: string
  name: string
  description: string
  rules: LuxianRuleOption[]
  ruleIds: string[]
}

export type SamplePoolRunPayload = {
  sample_item_ids?: string[]
  record_refs?: Array<{
    institute_id: string
    patient_id: string
    visit_id: string
  }>
  max_parallel_records: number
  validation_mode: ManualSampleValidationMode
  rule_set_key: string
  selected_rule_ids?: string[]
  group_by_luxian_family?: boolean
}

export type LuxianFamilyRunScope = {
  key: string
  name: string
  ruleIds: string[]
}

export type LuxianAggregateJob = {
  family: LuxianFamilyRunScope
  jobId: string
  status: SichuanBatchJobStatus
  detail?: SichuanBatchJob
  errorMessage?: string
}

export type EditableCopyDraft = {
  caseTitle: string
  patientName: string
  sex: string
  age: number
  mrNo: string
  department: string
  admissionTime: string
  dischargeTime: string
  mainDiagnosis: string
  manualIssueText: string
  documents: EditableMedicalRecordDocument[]
}

export type EditableCopyDocumentFilter = 'all' | 'enabled' | 'orders' | 'new'

export type EditableCopyDocumentGroup = {
  key: string
  label: string
  documents: EditableMedicalRecordDocument[]
}

export const LUXIAN_0609_RULE_FAMILY_DEFINITIONS = [
  {
    key: 'basic_timeliness',
    name: '基础时限',
    description: '覆盖入院记录、首次病程、抢救记录和上级医师首次查房时限。',
    ruleIds: ['LX0609-001', 'LX0609-002', 'LX0609-004', 'LX0609-005', 'LX0609-006'],
  },
  {
    key: 'course_quality',
    name: '查房病程',
    description: '覆盖查房频次、病程复制、主诉和诊断依据等病程质量问题。',
    ruleIds: ['LX0609-007', 'LX0609-008', 'LX0609-009', 'LX0609-016', 'LX0609-017', 'LX0609-018'],
  },
  {
    key: 'exam_lab',
    name: '检查检验',
    description: '覆盖 CT/MRI、细菌培养结果记录与阳性结果分析。',
    ruleIds: ['LX0609-010', 'LX0609-011', 'LX0609-012', 'LX0609-014', 'LX0609-015'],
  },
  {
    key: 'consultation_quality',
    name: '会诊质量',
    description: '覆盖会诊目的、会诊意见和会诊执行记录。',
    ruleIds: ['LX0609-020', 'LX0609-021', 'LX0609-022', 'LX0609-023'],
  },
  {
    key: 'surgery_anesthesia',
    name: '手术麻醉',
    description: '覆盖手术记录、术前小结、知情同意、核查表、麻醉记录和术前讨论。',
    ruleIds: [
      'LX0609-003',
      'LX0609-024',
      'LX0609-025',
      'LX0609-028',
      'LX0609-029',
      'LX0609-030',
      'LX0609-031',
      'LX0609-032',
      'LX0609-033',
      'LX0609-034',
      'LX0609-035',
      'LX0609-036',
      'LX0609-037',
      'LX0609-038',
      'LX0609-039',
      'LX0609-040',
    ],
  },
  {
    key: 'transfusion',
    name: '输血',
    description: '覆盖输血知情同意、输血前检查、输血前后评价和医嘱收费一致性。',
    ruleIds: [
      'LX0609-041',
      'LX0609-042',
      'LX0609-043',
      'LX0609-044',
      'LX0609-045',
      'LX0609-046',
      'LX0609-047',
      'LX0609-048',
      'LX0609-049',
    ],
  },
  {
    key: 'tumor_pathology',
    name: '肿瘤病理',
    description: '覆盖病理结果、取材情况、化疗记录和肿瘤出院治疗计划。',
    ruleIds: ['LX0609-013', 'LX0609-019', 'LX0609-026', 'LX0609-027'],
  },
] as const

export type CustomerSampleGuideTarget =
  | 'sample-pool'
  | 'sample-rule'
  | 'lx0609-scope'
  | 'create-record'
  | 'record-list'
  | 'run-validation'

export type ImportWorkflowState = {
  poolId: string
  poolName: string
  importedRows: number
  matching: boolean
  matched: number
  ambiguous: number
  unmatched: number
  status:
    | 'imported'
    | 'matching'
    | 'matched'
    | 'no_match'
    | 'match_failed'
    | 'syncing'
    | 'synced'
    | 'sync_failed'
  message: string
}

export const customerSampleGuideSteps: Array<{
  target: CustomerSampleGuideTarget
  title: string
  description: string
}> = [
  {
    target: 'sample-pool',
    title: '先选择样本池',
    description:
      '这里切换要验证的病历来源：客户自建测试病历用于现场演示，泸县0609合成质控样本用于回归验证，真实样本池用于客户数据复核。',
  },
  {
    target: 'sample-rule',
    title: '确认验证规则集',
    description:
      '这里选择本次运行的规则包。客户演示优先使用泸县0609质控点验证，页面会显示规则数量和覆盖状态。',
  },
  {
    target: 'lx0609-scope',
    title: '限定 LX0609 质控点范围',
    description: '默认运行全量 0609；勾选质控点后，只验证选中的 LX0609 客户质控点。',
  },
  {
    target: 'create-record',
    title: '创建测试病历',
    description: '点击这里可按质控点生成测试病历，保存后回到病历池继续验证。',
  },
  {
    target: 'record-list',
    title: '勾选要验证的病历',
    description: '在病历池中搜索、筛选并勾选病历；未选择病历时页面会提示先选择。',
  },
  {
    target: 'run-validation',
    title: '查看任务结果与证据链',
    description: '发起验证后打开结果抽屉，查看进度、状态分布、命中的客户质控点和证据摘要。',
  },
]

export const fallbackRuleSets: ManualSampleValidationRuleSet[] = [
  {
    rule_set_key: LUXIAN_0609_RULE_SET_KEY,
    rule_set_name: '泸县0609质控点验证 v1',
    rule_set_version: '2026-06-09',
    scope: 'running',
    rule_count: 59,
    validation_mode: 'customer',
    advanced: false,
    display_group: 'main',
    coverage_summary: {
      已达正式口径: 6,
      证据待补强: 10,
      跨文书待完善: 14,
      跨表联查待接入: 15,
      待实现规则: 4,
    },
    coverage_status:
      '正式上线闸门未通过：通过 3 项，失败 6 项，未验证 0 项；当前 6 条达到 formal_ready，其余规则仍需补证据、跨文书或跨表执行链路。',
    release_gate_summary: {
      release_ready: false,
      passed_checks: 3,
      failed_checks: 6,
      unverified_checks: 0,
      blocking_count: 6,
    },
    evaluation_summary: {
      rule_count: 49,
      rules_with_all_case_types: 0,
      rules_missing_case_types: 49,
      hit_count: 0,
      manual_confirmed_correct_count: 0,
      false_positive_count: 0,
      false_negative_count: 0,
      unknown_count: 0,
      evidence_missing_count: 0,
      launch_status: { not_ready: 49 },
    },
    work_package_summary: {
      package_count: 49,
      phase_counts: {
        阶段3样本验证集建设: 6,
        阶段2证据链补强: 10,
        阶段2跨文书执行链路: 14,
        阶段2跨表数据联查: 15,
        阶段2新增规则实现: 4,
      },
      priority_counts: {
        P0: 14,
        P1: 22,
        P2: 13,
      },
    },
    page_closure_summary: {
      page_verified: false,
      capability_count: 8,
      passed_capabilities: 4,
      partial_capabilities: 4,
      failed_capabilities: 0,
      blocking_count: 4,
      status_counts: {
        pass: 4,
        partial: 4,
      },
    },
    note: '客户第一批专项验证规则包；当前为验证版，未达到正式上线闸门。',
  },
  {
    rule_set_key: FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    rule_set_name: 'SC 内涵质控全量 v1',
    rule_set_version: '2026-04-20',
    scope: 'final',
    rule_count: 84,
    validation_mode: 'formal_fast_screen_full',
    requires_synced: true,
    advanced: false,
    display_group: 'main',
    coverage_status: 'SC146 中 84 条内涵规则全量基线',
    note: '正式终末内涵质控全量规则，用于与客户专项验证结果做基线对照。',
  },
  {
    rule_set_key: SC_SAMPLE_RULE_SET_KEY,
    rule_set_name: 'SC 样本规则模式',
    rule_set_version: 'running-batch-1',
    scope: 'running',
    rule_count: 0,
    validation_mode: 'sc',
    advanced: true,
    display_group: 'advanced',
    coverage_status: '规则数量由样本候选规则动态决定',
  },
  {
    rule_set_key: PROGRAMMATIC_RULE_SET_KEY,
    rule_set_name: '样本硬门槛程序规则包 v1',
    rule_set_version: '2026-04-27',
    scope: 'running',
    rule_count: 17,
    validation_mode: 'programmatic',
    requires_synced: true,
    advanced: true,
    display_group: 'advanced',
    coverage_status: '固定程序硬门槛规则包',
  },
  {
    rule_set_key: LEGACY_CUSTOMER_RULE_SET_KEY,
    rule_set_name: '客户专项规则包 v1（历史）',
    rule_set_version: '2026-04-30',
    scope: 'running',
    rule_count: 0,
    validation_mode: 'customer',
    advanced: true,
    display_group: 'advanced',
    coverage_status: '历史客户包，仅用于兼容旧样本复现',
  },
]
