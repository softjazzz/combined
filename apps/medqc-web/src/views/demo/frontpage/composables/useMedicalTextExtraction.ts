import type { Ref } from 'vue'
import { ref } from 'vue'
import { message, notification } from 'ant-design-vue'

export interface DemoCaseLike {
  case_id: string
  description?: string
  medical_text?: string
  frontpage?: any
  insurance_claim?: any
}

export function useMedicalTextExtraction(options: {
  demoCase: Ref<DemoCaseLike | null>
  onStartExtract?: () => void
  onExtracted?: () => void
}) {
  const extracting = ref(false)

  const applyFrontpageResult = (fp: any) => {
    if (!options.demoCase.value) return

    // Preserve all original backend fields and add transformed fields for backward compatibility
    options.demoCase.value.frontpage = {
      // Spread all original backend data
      ...fp,

      // Override/enhance specific sections with both original and transformed field names
      basic_info: {
        ...fp.basic_info,
        // Transformed fields for backward compatibility
        native_place: fp.basic_info?.current_address || '',
        marriage: fp.basic_info?.marital_status_text || '',
        job: fp.basic_info?.occupation || ''
      },
      hospitalization: {
        ...fp.hospitalization,
        // Transformed fields for backward compatibility
        admission_date: fp.hospitalization?.admission_datetime || '',
        discharge_date: fp.hospitalization?.discharge_datetime || '',
        hospital_days: fp.hospitalization?.actual_hospital_days || 0,
        admitted_dept: fp.hospitalization?.admission_dept || '',
        discharged_dept: fp.hospitalization?.discharge_dept || '',
        admission_way: fp.hospitalization?.admission_way_text || '',
        leaving_way: '医嘱离院'
      },
      diagnoses: {
        ...fp.diagnoses,
        // Transformed fields for backward compatibility
        admission_main_conn: String(fp.diagnoses?.admission_condition ?? '') === '1' ? '有' : '-',
        discharge_main_conn: '有',
        // Legacy format for other diagnoses
        discharge_other_diagnoses: (
          fp.diagnoses?.discharge_other_diagnoses_texts?.length > 0
            ? fp.diagnoses.discharge_other_diagnoses_texts
            : fp.diagnoses?.ed_diagnosis_texts?.slice(1) || []
        ).map((name: string, idx: number) => ({
          name,
          code: fp.diagnoses?.discharge_other_icds?.[idx] || '待编码',
          conn: '有'
        }))
      },
      procedures: {
        ...fp.procedures,
        // Transformed format for StructuredDataView table display
        main: {
          name: fp.procedures?.main_procedure_text || '无',
          code: fp.procedures?.main_procedure_code || '',
          date: fp.procedures?.main_procedure_date || '',
          surgeon: fp.procedures?.surgeon_name || '',
          anesthesia: fp.procedures?.anesthesia_method || '',
          level: fp.procedures?.main_procedure_level || ''
        },
        others: []
      },
      staff: {
        ...fp.staff
      },
      costs: {
        ...fp.costs
      },
      other_medical_info: {
        ...fp.other_medical_info
      },
      // Transformed fields for backward compatibility
      quality: {
        director: fp.staff?.dept_director || '',
        chief_doctor: fp.staff?.chief_physician || '',
        attending_doctor: fp.staff?.attending_physician || '',
        coder: 'AI 预编'
      }
    }

    options.demoCase.value.insurance_claim = {
      settlement_id: 'SET' + Date.now(),
      insurance_type: fp.hospitalization?.payment_method_text || '城镇职工基本医疗保险',
      total_cost: fp.costs?.total_cost || 0,
      fund_pay: fp.costs?.total_cost ? fp.costs.total_cost * 0.8 : 0,
      patient_pay: fp.costs?.self_paid || 0
    }

    // ===== DRG 分组所需的额外字段 =====
    // 映射到 DRG API 期望的格式
    const frontpageForDRG = options.demoCase.value.frontpage as any

    // 主诊断编码（DRG 分组必需）
    frontpageForDRG.primary_diagnosis_code = fp.diagnoses?.discharge_main_icd || null
    frontpageForDRG.primary_diagnosis_name = fp.diagnoses?.discharge_main_diagnosis_text || null

    // 次要诊断（数组格式）
    const otherTexts = fp.diagnoses?.discharge_other_diagnoses_texts || []
    const otherCodes = fp.diagnoses?.discharge_other_icds || []
    frontpageForDRG.secondary_diagnoses = otherTexts.map((name: string, idx: number) => ({
      code: otherCodes[idx] || '待编码',
      name: name
    }))

    // 主要手术/操作编码
    frontpageForDRG.main_procedure_code = fp.procedures?.main_procedure_code || null
    frontpageForDRG.main_procedure_name = fp.procedures?.main_procedure_text || null

    // 其他手术操作
    frontpageForDRG.procedures_list = (fp.procedures?.other_procedures || []).map((p: any) => ({
      code: p.code || '待编码',
      name: p.text || p.name || ''
    }))

    // 患者年龄和性别（DRG 分组需要）
    frontpageForDRG.patient_age = fp.basic_info?.age_years || 0
    frontpageForDRG.patient_gender = fp.basic_info?.gender === '1' ? 'M' : 'F'

    // 住院天数
    frontpageForDRG.total_hospital_days = fp.hospitalization?.actual_hospital_days || 0

    // 实际费用（用于盈亏计算）
    frontpageForDRG.total_cost = fp.costs?.total_cost || 0
  }

  const useMockFallback = () => {
    const mockFrontpage = {
      basic_info: {
        patient_name: '张三',
        gender_text: '男',
        age_years: 58,
        birth_date: '1966-01-15',
        id_number: '510102196601151234',
        nationality: '中国',
        native_place: '四川成都',
        marriage: '已婚',
        job: '退休人员'
      },
      hospitalization: {
        admission_date: '2025-12-28 09:30',
        discharge_date: '2026-01-04 10:00',
        hospital_days: 7,
        admitted_dept: '心血管内科',
        discharged_dept: '心血管内科',
        admission_way: '急诊',
        leaving_way: '医嘱离院'
      },
      diagnoses: {
        discharge_main_diagnosis_text: '高血压3级 极高危',
        discharge_main_icd: 'I10.x00',
        discharge_main_conn: '有',
        discharge_other_diagnoses: [
          { name: '2型糖尿病', code: 'E11.900', conn: '有' },
          { name: '冠状动脉粥样硬化性心脏病', code: 'I25.100', conn: '有' },
          { name: '高脂血症', code: 'E78.500', conn: '有' }
        ]
      },
      procedures: {
        main: {
          name: '冠状动脉造影术',
          code: '88.55',
          date: '2026-01-02',
          surgeon: '李医生',
          anesthesia: '局麻',
          level: 'III级'
        },
        others: []
      },
      quality: {
        director: '王院长',
        chief_doctor: '赵主任',
        attending_doctor: '李医生',
        coder: '张编码'
      }
    }

    if (!options.demoCase.value) return
    options.demoCase.value.frontpage = mockFrontpage
    options.demoCase.value.insurance_claim = {
      settlement_id: 'SET2026010001',
      insurance_type: '城镇职工基本医疗保险',
      total_cost: 12580.5,
      fund_pay: 10064.4,
      patient_pay: 2516.1
    }
  }

  const extractStructuredData = async () => {
    if (!options.demoCase.value?.medical_text) {
      message.warning('请先加载病历原文')
      return
    }

    const medicalText = options.demoCase.value.medical_text

    extracting.value = true
    options.onStartExtract?.()

    // Track completed modules for progress display
    const completedModules: string[] = []
    const moduleNames: Record<string, string> = {
      basic_info: '基本信息',
      hospitalization: '住院信息',
      diagnoses: '诊断信息',
      procedures: '手术操作',
      other_medical_info: '其他医疗信息',
      staff: '人员信息',
      costs: '费用信息',
      coding_result: 'ICD 编码'
    }

    try {
      // Use SSE stream API for progressive display
      const response = await fetch('/api/v1/frontpage/auto-generate-draft-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medical_text: medicalText })
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        let eventType = ''
        let eventData = ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            eventData = line.slice(5).trim()
          } else if (line === '' && eventType && eventData) {
            // End of event, process it
            try {
              const parsed = JSON.parse(eventData)

              if (eventType === 'update' && parsed.frontpage) {
                // Progressive update - apply partial results immediately
                applyFrontpageResult(parsed.frontpage)

                // Track and show progress
                if (parsed.module && !completedModules.includes(parsed.module)) {
                  completedModules.push(parsed.module)
                  const moduleName = moduleNames[parsed.module] || parsed.module
                  console.log(`✓ ${moduleName} 提取完成`)
                }
              } else if (eventType === 'done' && parsed.frontpage) {
                // Final complete result
                applyFrontpageResult(parsed.frontpage)

                // Check for warnings
                if (parsed.frontpage.confidence?.warnings?.length > 0) {
                  const count = parsed.frontpage.confidence.warnings.length
                  setTimeout(() => {
                    message.warning({
                      content: `发现 ${count} 条编码校验警告，请仔细核对诊断编码`,
                      duration: 5
                    })
                  }, 500)
                }

                // Show prominent completion notification
                notification.success({
                  message: '✅ AI 提取完成',
                  description: `已成功提取 ${completedModules.length} 个模块的结构化数据，包括诊断编码和手术编码。`,
                  duration: 5,
                  placement: 'topRight'
                })
                options.onExtracted?.()
              } else if (eventType === 'error') {
                console.error('SSE error:', parsed)
                throw new Error(parsed.error || 'Stream error')
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE data:', eventData, parseError)
            }

            // Reset for next event
            eventType = ''
            eventData = ''
          }
        }
      }
    } catch (error: any) {
      console.error('结构化提取失败:', error)
      useMockFallback()
      message.warning('网络请求失败，已使用模拟数据')
      options.onExtracted?.()
    } finally {
      extracting.value = false
    }
  }

  return {
    extracting,
    extractStructuredData
  }
}
