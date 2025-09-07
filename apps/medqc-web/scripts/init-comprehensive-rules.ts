import { createClient } from '@supabase/supabase-js'
import type { Database } from '../src/types/supabase'
import { config } from 'dotenv'

// 加载环境变量
config()

// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient<Database>(supabaseUrl, supabaseServiceKey)

// 质控规则接口定义
interface QCRuleInsert {
  rule_code: string
  name: string
  description: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  prompt_template?: string
  check_logic: Record<string, any>
  is_active: boolean
  version: string
}

// 综合质控规则集 - 涵盖医疗质量管理的各个方面
const comprehensiveRules: QCRuleInsert[] = [
  // ========== 完整性规则 (Completeness Rules) ==========
  {
    rule_code: '2.1.1',
    name: '患者基本信息完整性检查',
    description: '检查患者姓名、性别、年龄、身份证号、联系方式等基本信息是否完整',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0, // 单否项
    weight: 1.0,
    is_active: true,
    check_logic: {
      required_fields: ['patient_name', 'gender', 'age', 'id_number', 'contact_phone'],
      validation_rules: {
        patient_name: { min_length: 2, max_length: 50, pattern: '^[\\u4e00-\\u9fa5a-zA-Z\\s]+$' },
        gender: { enum: ['男', '女', '未知'] },
        age: { min: 0, max: 150, type: 'integer' },
        id_number: { pattern: '^[1-9]\\d{5}(18|19|20)\\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\\d{3}[0-9Xx]$' },
        contact_phone: { pattern: '^1[3-9]\\d{9}$' }
      }
    },
    prompt_template: '请检查患者基本信息是否完整，包括姓名、性别、年龄、身份证号、联系电话等必填项。姓名应为中文或英文，年龄应在合理范围内，身份证号格式应正确。',
    version: '2.0'
  },
  {
    rule_code: '2.1.2',
    name: '入院记录完整性检查',
    description: '检查入院记录各项内容是否完整，包括主诉、现病史、既往史、体格检查等',
    category: 'completeness',
    rule_type: 'hybrid',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    is_active: true,
    check_logic: {
      required_sections: [
        'chief_complaint',
        'present_illness_history', 
        'past_medical_history',
        'physical_examination',
        'admission_diagnosis'
      ],
      section_requirements: {
        chief_complaint: { min_length: 5, max_length: 200 },
        present_illness_history: { min_length: 20, max_length: 2000 },
        past_medical_history: { min_length: 5, max_length: 500 },
        physical_examination: { min_length: 50, max_length: 1000 },
        admission_diagnosis: { min_length: 3, max_length: 300 }
      }
    },
    prompt_template: '请检查入院记录是否完整，包括：1)主诉(简明扼要)；2)现病史(详细描述)；3)既往史；4)体格检查(系统全面)；5)入院诊断。每个部分都应有实质性内容，不能为空或过于简单。',
    version: '2.0'
  },
  {
    rule_code: '2.1.3',
    name: '出院记录完整性检查',
    description: '检查出院记录是否完整，包括入院情况、诊疗经过、出院诊断、出院医嘱等',
    category: 'completeness',
    rule_type: 'hybrid',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    is_active: true,
    check_logic: {
      required_sections: [
        'admission_condition',
        'treatment_process',
        'discharge_diagnosis',
        'discharge_orders',
        'discharge_guidance'
      ],
      section_requirements: {
        admission_condition: { min_length: 10, max_length: 300 },
        treatment_process: { min_length: 50, max_length: 2000 },
        discharge_diagnosis: { min_length: 5, max_length: 500 },
        discharge_orders: { min_length: 10, max_length: 500 },
        discharge_guidance: { min_length: 20, max_length: 1000 }
      }
    },
    prompt_template: '请检查出院记录完整性：1)入院情况概述；2)诊疗经过(治疗措施、病情变化)；3)出院诊断(主要诊断、其他诊断)；4)出院医嘱；5)出院指导(用药、复查、注意事项)。',
    version: '2.0'
  },
  {
    rule_code: '2.1.4',
    name: '手术记录完整性检查',
    description: '检查手术记录是否完整，包括术前诊断、手术指征、手术过程、术后处理等',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 10,
    weight: 0.9,
    is_active: true,
    check_logic: {
      conditional_check: {
        condition: 'has_surgery == true',
        required_fields: [
          'preop_diagnosis',
          'surgery_indication',
          'surgery_procedure',
          'postop_treatment',
          'surgeon_name',
          'assistant_names',
          'anesthesia_type',
          'surgery_date',
          'surgery_duration'
        ]
      }
    },
    prompt_template: '如果患者进行了手术，请检查手术记录完整性：术前诊断、手术指征、手术过程描述、术后处理、手术医师、助手、麻醉方式、手术时间和持续时间等信息是否完整。',
    version: '2.0'
  },
  {
    rule_code: '2.1.5',
    name: '医嘱执行记录完整性检查',
    description: '检查医嘱的开具、执行、停止记录是否完整规范',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 8,
    weight: 1.0,
    is_active: true,
    check_logic: {
      required_elements: [
        'order_content',
        'order_time',
        'doctor_signature',
        'execution_time',
        'nurse_signature'
      ],
      validation_rules: {
        order_content: { min_length: 3, max_length: 200 },
        order_time: { format: 'datetime' },
        execution_time: { format: 'datetime' },
        doctor_signature: { min_length: 2, max_length: 20 },
        nurse_signature: { min_length: 2, max_length: 20 }
      }
    },
    prompt_template: '请检查医嘱记录完整性：医嘱内容清晰、开具时间准确、医师签名完整、执行时间记录、护士签名等要素是否齐全。',
    version: '2.0'
  },

  // ========== 一致性规则 (Consistency Rules) ==========
  {
    rule_code: '2.2.1',
    name: '诊断一致性检查',
    description: '检查入院诊断、出院诊断、手术诊断之间的一致性',
    category: 'consistency',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 15,
    weight: 1.0,
    is_active: true,
    check_logic: {
      comparison_fields: [
        'admission_diagnosis',
        'discharge_diagnosis',
        'surgery_diagnosis'
      ],
      consistency_rules: {
        main_diagnosis_consistency: { threshold: 0.8 },
        icd_code_consistency: { strict_match: true },
        diagnosis_evolution: { logical_progression: true }
      }
    },
    prompt_template: '请检查诊断一致性：1)入院诊断与出院诊断的逻辑关系；2)手术诊断与其他诊断的一致性；3)诊断的演变是否符合疾病发展规律；4)ICD编码是否一致。',
    version: '2.0'
  },
  {
    rule_code: '2.2.2',
    name: '时间逻辑一致性检查',
    description: '检查病历中各时间节点的逻辑一致性',
    category: 'consistency',
    rule_type: 'objective',
    severity: 'major',
    max_score: 12,
    weight: 0.8,
    is_active: true,
    check_logic: {
      time_sequence_check: {
        required_order: [
          'admission_time',
          'first_course_record_time',
          'surgery_time',
          'discharge_time'
        ],
        max_intervals: {
          'admission_to_first_record': { hours: 24 },
          'surgery_to_postop_record': { hours: 6 },
          'last_record_to_discharge': { hours: 24 }
        }
      }
    },
    prompt_template: '请检查时间逻辑一致性：入院时间、首次病程记录时间、手术时间、出院时间等是否符合逻辑顺序，时间间隔是否合理。',
    version: '2.0'
  },

  // ========== 合理性规则 (Rationality Rules) ==========
  {
    rule_code: '2.3.1',
    name: '药物使用合理性检查',
    description: '检查药物使用的适应症、剂量、疗程是否合理',
    category: 'rationality',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 20,
    weight: 1.0,
    is_active: true,
    check_logic: {
      drug_analysis: {
        check_indication: true,
        check_dosage: true,
        check_duration: true,
        check_interaction: true,
        check_contraindication: true
      },
      severity_levels: {
        contraindication: 'critical',
        overdose: 'major',
        inappropriate_indication: 'minor'
      }
    },
    prompt_template: '请检查药物使用合理性：1)药物适应症是否符合诊断；2)剂量是否适当；3)疗程是否合理；4)是否存在药物相互作用；5)是否有禁忌症。',
    version: '2.0'
  },
  {
    rule_code: '2.3.2',
    name: '检查检验合理性检查',
    description: '检查各项检查检验项目的必要性和合理性',
    category: 'rationality',
    rule_type: 'hybrid',
    severity: 'minor',
    max_score: 10,
    weight: 1.0,
    is_active: true,
    check_logic: {
      examination_analysis: {
        check_necessity: true,
        check_repetition: true,
        check_timing: true,
        check_cost_effectiveness: true
      },
      guidelines_compliance: {
        follow_clinical_guidelines: true,
        evidence_based: true
      }
    },
    prompt_template: '请检查检查检验合理性：1)检查项目是否必要；2)是否存在重复检查；3)检查时机是否合适；4)是否符合临床指南要求。',
    version: '2.0'
  },

  // ========== 及时性规则 (Timeliness Rules) ==========
  {
    rule_code: '2.4.1',
    name: '病程记录及时性检查',
    description: '检查病程记录是否按规定时间及时书写',
    category: 'timeliness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 8,
    weight: 1.0,
    is_active: true,
    check_logic: {
      timing_requirements: {
        first_course_record: { max_hours_after_admission: 8 },
        daily_course_record: { required_daily: true },
        critical_condition_record: { max_hours: 2 },
        preop_record: { max_hours_before_surgery: 24 },
        postop_record: { max_hours_after_surgery: 6 }
      }
    },
    prompt_template: '请检查病程记录及时性：首次病程记录应在入院8小时内完成，日常病程记录应每日书写，危重患者记录应及时，术前术后记录应按时完成。',
    version: '2.0'
  },
  {
    rule_code: '2.4.2',
    name: '医嘱执行及时性检查',
    description: '检查医嘱执行是否及时，特别是急诊医嘱和临时医嘱',
    category: 'timeliness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 12,
    weight: 0.8,
    is_active: true,
    check_logic: {
      execution_timing: {
        emergency_orders: { max_minutes: 15 },
        temporary_orders: { max_hours: 2 },
        routine_orders: { max_hours: 4 },
        stat_orders: { max_minutes: 30 }
      }
    },
    prompt_template: '请检查医嘱执行及时性：急诊医嘱应15分钟内执行，临时医嘱应2小时内执行，常规医嘱应4小时内执行，立即执行医嘱应30分钟内完成。',
    version: '2.0'
  }
]

// 初始化综合规则的主函数
async function initComprehensiveRules() {
  console.log('开始初始化综合质控规则...')
  
  try {
    // 检查现有规则，避免重复插入
    const { data: existingRules, error: fetchError } = await supabase
      .from('qc_rules')
      .select('rule_code')
    
    if (fetchError) {
      throw fetchError
    }
    
    const existingCodes = new Set(existingRules?.map(r => r.rule_code) || [])
    const newRules = comprehensiveRules.filter(rule => !existingCodes.has(rule.rule_code))
    
    if (newRules.length === 0) {
      console.log('所有综合规则已存在，无需重复插入')
      return
    }
    
    console.log(`准备插入 ${newRules.length} 条新规则...`)
    
    // 批量插入新规则
    const { data, error } = await supabase
      .from('qc_rules')
      .insert(newRules)
      .select()
    
    if (error) {
      throw error
    }
    
    console.log(`✅ 成功插入 ${data?.length || 0} 条综合质控规则`)
    
    // 输出插入的规则统计
    const stats = {
      completeness: newRules.filter(r => r.category === 'completeness').length,
      consistency: newRules.filter(r => r.category === 'consistency').length,
      rationality: newRules.filter(r => r.category === 'rationality').length,
      timeliness: newRules.filter(r => r.category === 'timeliness').length
    }
    
    console.log('规则分类统计:')
    console.log(`- 完整性规则: ${stats.completeness} 条`)
    console.log(`- 一致性规则: ${stats.consistency} 条`)
    console.log(`- 合理性规则: ${stats.rationality} 条`)
    console.log(`- 及时性规则: ${stats.timeliness} 条`)
    
  } catch (error) {
    console.error('❌ 初始化综合质控规则失败:', error)
    throw error
  }
}

// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
  initComprehensiveRules()
    .then(() => {
      console.log('综合质控规则初始化完成')
      process.exit(0)
    })
    .catch((error) => {
      console.error('初始化失败:', error)
      process.exit(1)
    })
}

export { initComprehensiveRules, comprehensiveRules }
