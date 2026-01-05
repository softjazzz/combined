import type { Ref } from 'vue'
import { ref } from 'vue'
import { message } from 'ant-design-vue'

export interface DemoCaseLike {
  case_id: string
  description?: string
  medical_text?: string
  frontpage?: any
  insurance_claim?: any
}

export function useMedicalTextExtraction(options: {
  demoCase: Ref<DemoCaseLike | null>
  onExtracted?: () => void
}) {
  const extracting = ref(false)

  const applyFrontpageResult = (fp: any) => {
    if (!options.demoCase.value) return

    options.demoCase.value.frontpage = {
      basic_info: {
        patient_name: fp.basic_info?.patient_name || '未识别',
        gender_text: fp.basic_info?.gender_text || '未知',
        age_years: fp.basic_info?.age_years || 0,
        birth_date: fp.basic_info?.birth_date || '',
        id_number: fp.basic_info?.id_number || '',
        nationality: fp.basic_info?.nationality || '',
        native_place: fp.basic_info?.current_address || '',
        marriage: fp.basic_info?.marital_status_text || '',
        job: fp.basic_info?.occupation || ''
      },
      hospitalization: {
        admission_date: fp.hospitalization?.admission_datetime || '',
        discharge_date: fp.hospitalization?.discharge_datetime || '',
        hospital_days: fp.hospitalization?.actual_hospital_days || 0,
        admitted_dept: fp.hospitalization?.admission_dept || '',
        discharged_dept: fp.hospitalization?.discharge_dept || '',
        admission_way: fp.hospitalization?.admission_way_text || '',
        leaving_way: '医嘱离院'
      },
      diagnoses: {
        // 入院诊断
        admission_main_diagnosis_text: fp.diagnoses?.admission_main_diagnosis_text || null,
        admission_main_icd: fp.diagnoses?.admission_main_icd || null,
        admission_main_conn: fp.diagnoses?.admission_condition === 1 ? '有' : '-',
        admission_other_diagnoses_texts: fp.diagnoses?.admission_other_diagnoses_texts || [],
        admission_other_icds: fp.diagnoses?.admission_other_icds || [],

        // 出院诊断
        discharge_main_diagnosis_text: fp.diagnoses?.discharge_main_diagnosis_text || null,
        discharge_main_icd: fp.diagnoses?.discharge_main_icd || null,
        discharge_main_conn: '有',
        discharge_other_diagnoses_texts: fp.diagnoses?.discharge_other_diagnoses_texts || [],
        discharge_other_icds: fp.diagnoses?.discharge_other_icds || [],

        // 向后兼容：保留旧的 discharge_other_diagnoses 数组格式
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
      quality: {
        director: fp.staff?.director || '',
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

    extracting.value = true
    try {
      const response = await fetch('/api/v1/case-front-page/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medical_text: options.demoCase.value.medical_text
        })
      })

      const data = await response.json()

      if (response.ok && data.success && data.data) {
        const fp = data.data.frontpage || data.data
        applyFrontpageResult(fp)

        if (fp.confidence?.warnings?.length > 0) {
          const count = fp.confidence.warnings.length
          setTimeout(() => {
            message.warning({
              content: `发现 ${count} 条编码校验警告，请仔细核对诊断编码`,
              duration: 5
            })
            console.warn('编码校验警告:', fp.confidence.warnings)
          }, 500)
        }

        message.success('AI 病案首页提取完成')
        options.onExtracted?.()
      } else {
        console.warn('LLM 提取失败，使用模拟数据:', data.error || data.detail || 'Unknown error')
        useMockFallback()
        message.warning('LLM 服务暂不可用，已使用模拟数据')
        options.onExtracted?.()
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

