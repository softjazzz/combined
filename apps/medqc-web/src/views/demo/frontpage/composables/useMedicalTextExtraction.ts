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
  // 'idle' | 'extracting' | 'completed' | 'mock_fallback'
  const extractionStatus = ref<'idle' | 'extracting' | 'completed' | 'mock_fallback'>('idle')
  const extractionProgress = ref<{
    completed: string[]
    currentModule: string
    total: number
    percent: number
  }>({
    completed: [],
    currentModule: '',
    total: 8,
    percent: 0
  })

  const MODULE_NAMES: Record<string, string> = {
    basic_info: '基本信息',
    hospitalization: '住院信息',
    diagnoses: '诊断信息',
    procedures: '手术操作',
    other_medical_info: '其他医疗信息',
    staff: '人员信息',
    costs: '费用信息',
    coding_result: 'ICD 编码',
    confidence: '置信度校验'
  }

  const sseDebugEnabled = false

  const sseLog = (requestId: string, ...args: any[]) => {
    if (!sseDebugEnabled) return
    console.log(`[frontpage-sse:${requestId}]`, ...args)
  }

  const sseError = (requestId: string, ...args: any[]) => {
    if (!sseDebugEnabled) return
    console.error(`[frontpage-sse:${requestId}]`, ...args)
  }

  const summarizeFrontpage = (fp: any) => ({
    patient_name: fp?.basic_info?.patient_name || null,
    gender_text: fp?.basic_info?.gender_text || null,
    main_diagnosis: fp?.diagnoses?.discharge_main_diagnosis_text || null,
    main_icd: fp?.diagnoses?.discharge_main_icd || null,
    main_procedure: fp?.procedures?.main_procedure_text || null,
    main_procedure_code: fp?.procedures?.main_procedure_code || null,
    total_cost: fp?.costs?.total_cost ?? null
  })

  const applyFrontpageResult = (fp: any, requestId?: string, source?: string) => {
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
        leaving_way: fp.hospitalization?.leaving_hospital_way || '医嘱离院',
        rehospital_within_month: fp.hospitalization?.rehospital_within_month || '无'
      },
      diagnoses: {
        ...fp.diagnoses,
        // Transformed fields for backward compatibility
        admission_main_conn: String(fp.diagnoses?.admission_condition ?? '') === '1' ? '有' : '-',
        discharge_main_conn: '有',
        discharge_main_outcome: fp.diagnoses?.discharge_main_outcome || '好转',
        // Legacy format for other diagnoses
        discharge_other_diagnoses: (
          fp.diagnoses?.discharge_other_diagnoses_texts || []
        ).map((name: string, idx: number) => ({
          name,
          code: fp.diagnoses?.discharge_other_icds?.[idx] || '待编码',
          conn: '有',
          outcome: fp.diagnoses?.discharge_other_outcomes?.[idx] || '好转'
        }))
      },
      procedures: {
        ...fp.procedures,
        // Transformed format for StructuredDataView table display
        main: {
          name: fp.procedures?.main_procedure_text || '无',
          code: fp.procedures?.main_procedure_code || '',
          date: fp.procedures?.main_procedure_date || '',
          start_time: fp.procedures?.main_procedure_start_time || '',
          end_time: fp.procedures?.main_procedure_end_time || '',
          surgeon: fp.procedures?.surgeon_name || '',
          anesthesia: fp.procedures?.anesthesia_method || '',
          level: fp.procedures?.main_procedure_level || '',
          incision_grade: fp.procedures?.incision_grade || '',
          anesthesia_grade: fp.procedures?.anesthesia_grade || ''
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
        coder: fp.staff?.coder || '待定',
        qc_physician: fp.staff?.qc_physician || '',
        qc_nurse: fp.staff?.qc_nurse || '',
        qc_date: fp.staff?.qc_date || '',
        qc_level: fp.staff?.medical_record_quality || ''
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

    if (requestId) {
      sseLog(requestId, `applyFrontpageResult(${source || 'unknown'})`, summarizeFrontpage(fp))
    }
  }

  const useMockFallback = (requestId?: string) => {
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

    if (requestId) {
      sseLog(requestId, 'useMockFallback applied')
    }
  }

  const extractStructuredData = async () => {
    if (!options.demoCase.value?.medical_text) {
      message.warning('请先加载病历原文')
      return
    }

    const medicalText = options.demoCase.value.medical_text
    const requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

    extracting.value = true
    extractionStatus.value = 'extracting'
    options.onStartExtract?.()
    sseLog(requestId, 'extractStructuredData:start', {
      case_id: options.demoCase.value.case_id,
      medical_text_length: medicalText.length
    })

    // Track completed modules for progress display
    const completedModules: string[] = []
    const moduleNames: Record<string, string> = MODULE_NAMES

    // Reset progress
    extractionProgress.value = {
      completed: [],
      currentModule: '正在初始化...',
      total: Object.keys(moduleNames).length,
      percent: 0
    }

    try {
      const tryNonStream = async (): Promise<boolean> => {
        try {
          sseLog(requestId, 'tryNonStream:start')
          const resp = await fetch('/api/v1/frontpage/auto-generate-draft', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ medical_text: medicalText })
          })
          sseLog(requestId, 'tryNonStream:response', {
            ok: resp.ok,
            status: resp.status,
            content_type: resp.headers.get('content-type'),
            trace_id: resp.headers.get('x-trace-id')
          })

          const json = await resp.json().catch(() => null)
          const fp = json?.data?.frontpage
          if (!fp) {
            sseLog(requestId, 'tryNonStream:no_frontpage_in_response')
            return false
          }

          applyFrontpageResult(fp, requestId, 'non-stream')

          // 更新进度到100%
          const allKeys = Object.keys(MODULE_NAMES)
          extractionProgress.value = {
            completed: allKeys,
            currentModule: '✅ 提取完成',
            total: allKeys.length,
            percent: 100
          }
          extractionStatus.value = 'completed'

          if (fp.confidence?.warnings?.length > 0) {
            const count = fp.confidence.warnings.length
            setTimeout(() => {
              message.warning({
                content: `发现 ${count} 条编码校验警告，请仔细核对诊断编码`,
                duration: 5
              })
            }, 500)
          }

          notification.success({
            message: '✅ AI 提取完成',
            description: `已成功提取结构化数据。`,
            duration: 5,
            placement: 'topRight'
          })
          sseLog(requestId, 'tryNonStream:success')
          options.onExtracted?.()
          return true
        } catch (nonStreamError) {
          sseError(requestId, 'tryNonStream:error', nonStreamError)
          return false
        }
      }

      // Use SSE stream API for progressive display.
      // All requests go through Vite proxy (relative path) to avoid CORS issues.
      const streamUrls = ['/api/v1/frontpage/auto-generate-draft-stream']

      const streamHeaderTimeoutMs = 30000
      let response: Response | null = null
      let lastStreamFetchError: any = null

      for (let i = 0; i < streamUrls.length; i += 1) {
        const streamUrl = streamUrls[i]
        const streamFetchStartAt = Date.now()
        sseLog(requestId, 'streamFetch:start', {
          attempt: i + 1,
          url: streamUrl,
          timeout_ms: streamHeaderTimeoutMs
        })

        const controller = new AbortController()
        const timeoutId = window.setTimeout(() => controller.abort('stream_header_timeout'), streamHeaderTimeoutMs)
        const waitingTimer = window.setInterval(() => {
          sseLog(requestId, 'streamFetch:waiting_headers', {
            attempt: i + 1,
            url: streamUrl,
            elapsed_ms: Date.now() - streamFetchStartAt
          })
        }, 3000)

        try {
          const candidate = await fetch(streamUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'text/event-stream',
              'Cache-Control': 'no-cache'
            },
            body: JSON.stringify({ medical_text: medicalText }),
            signal: controller.signal
          })

          sseLog(requestId, 'streamFetch:response', {
            attempt: i + 1,
            url: streamUrl,
            elapsed_ms: Date.now() - streamFetchStartAt,
            ok: candidate.ok,
            status: candidate.status,
            status_text: candidate.statusText,
            content_type: candidate.headers.get('content-type'),
            trace_id: candidate.headers.get('x-trace-id'),
            transfer_encoding: candidate.headers.get('transfer-encoding')
          })
          response = candidate
          break
        } catch (streamFetchError: any) {
          lastStreamFetchError = streamFetchError
          sseError(requestId, 'streamFetch:request_error', {
            attempt: i + 1,
            url: streamUrl,
            elapsed_ms: Date.now() - streamFetchStartAt,
            name: streamFetchError?.name,
            message: streamFetchError?.message || String(streamFetchError)
          })
        } finally {
          window.clearTimeout(timeoutId)
          window.clearInterval(waitingTimer)
        }
      }

      if (!response) {
        sseError(requestId, 'streamFetch:all_attempts_failed', {
          attempts: streamUrls.length,
          last_error: lastStreamFetchError?.message || String(lastStreamFetchError)
        })
        if (await tryNonStream()) return
        throw lastStreamFetchError || new Error('All stream fetch attempts failed')
      }

      if (!response.ok || !response.body) {
        const raw = await response.text().catch(() => '')
        sseError(requestId, 'streamFetch:invalid_response', {
          status: response.status,
          raw_preview: raw.slice(0, 500)
        })
        console.warn('LLM 流式提取失败:', raw || `${response.status} ${response.statusText}` || 'Unknown error')
        if (await tryNonStream()) return
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body.getReader()

      const decoder = new TextDecoder()
      let buffer = ''
      let eventType = ''
      let eventData = ''
      let chunkCount = 0
      let totalBytes = 0

      while (true) {
        const { done, value } = await reader.read()
        chunkCount += 1
        if (value) totalBytes += value.byteLength
        sseLog(requestId, 'stream:chunk', {
          chunk: chunkCount,
          done,
          value_bytes: value?.byteLength || 0,
          total_bytes: totalBytes
        })
        if (done) {
          buffer += decoder.decode()
          // Force a final flush in case the stream closes without trailing blank line.
          buffer += '\n'
        } else {
          buffer += decoder.decode(value, { stream: true })
        }

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer
        if (lines.length > 0) {
          sseLog(requestId, 'stream:lines_ready', {
            lines: lines.length,
            remaining_buffer_length: buffer.length
          })
        }

        for (const line of lines) {
          const normalizedLine = line.replace(/\r$/, '')
          if (normalizedLine.startsWith('event:')) {
            eventType = normalizedLine.slice(6).trim()
            sseLog(requestId, 'stream:event_type', { eventType })
          } else if (normalizedLine.startsWith('data:')) {
            const chunk = normalizedLine.slice(5).trim()
            eventData = eventData ? `${eventData}\n${chunk}` : chunk
            sseLog(requestId, 'stream:data_chunk', {
              eventType,
              chunk_length: chunk.length,
              data_length: eventData.length
            })
          } else if (normalizedLine.startsWith(':')) {
            // SSE comment/heartbeat line
            sseLog(requestId, 'stream:heartbeat', normalizedLine)
            continue
          } else if (normalizedLine.trim() === '' && eventType && eventData) {
            // End of event, process it
            sseLog(requestId, 'stream:event_complete', {
              eventType,
              data_length: eventData.length,
              data_preview: eventData.slice(0, 200)
            })
            try {
              const parsed = JSON.parse(eventData)

              if (eventType === 'update' && parsed.frontpage) {
                // Progressive update - apply partial results immediately
                sseLog(requestId, 'stream:update_event', {
                  module: parsed.module || null,
                  keys: Object.keys(parsed.frontpage || {})
                })
                applyFrontpageResult(parsed.frontpage, requestId, `stream-update:${parsed.module || 'unknown'}`)

                // Track and show progress
                if (parsed.module && !completedModules.includes(parsed.module)) {
                  completedModules.push(parsed.module)
                  const moduleName = moduleNames[parsed.module] || parsed.module
                  sseLog(requestId, 'stream:module_completed', { module: parsed.module, moduleName })
                  // Update reactive progress
                  extractionProgress.value = {
                    completed: [...completedModules],
                    currentModule: moduleName,
                    total: Object.keys(moduleNames).length,
                    percent: Math.round((completedModules.length / Object.keys(moduleNames).length) * 100)
                  }
                }
              } else if (eventType === 'done' && parsed.frontpage) {
                // Final complete result
                sseLog(requestId, 'stream:done_event', {
                  completed_modules: completedModules,
                  keys: Object.keys(parsed.frontpage || {})
                })
                applyFrontpageResult(parsed.frontpage, requestId, 'stream-done')

                // 更新进度到100%
                const allKeys = Object.keys(moduleNames)
                extractionProgress.value = {
                  completed: allKeys,
                  currentModule: '✅ 提取完成',
                  total: allKeys.length,
                  percent: 100
                }
                extractionStatus.value = 'completed'

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
                sseError(requestId, 'stream:error_event', parsed)
                console.error('SSE error:', parsed)
                try {
                  await reader.cancel()
                } catch {
                  // ignore
                }
                if (await tryNonStream()) return
                throw new Error(parsed.error || 'Stream error')
              }
            } catch (parseError) {
              sseError(requestId, 'stream:event_process_error', {
                eventType,
                eventDataPreview: eventData.slice(0, 300),
                parseError
              })
              console.warn('Failed to parse SSE data:', eventData, parseError)
            }

            // Reset for next event
            eventType = ''
            eventData = ''
          }
        }

        if (done) {
          sseLog(requestId, 'stream:reader_done', {
            chunks: chunkCount,
            total_bytes: totalBytes,
            completed_modules: completedModules
          })
          break
        }
      }
    } catch (error: any) {
      sseError(requestId, 'extractStructuredData:error', error)
      console.error('结构化提取失败:', error)
      useMockFallback(requestId)
      // 模拟进度完成动画
      const allKeys = Object.keys(MODULE_NAMES)
      extractionProgress.value = {
        completed: allKeys,
        currentModule: '✅ 已使用模拟数据',
        total: allKeys.length,
        percent: 100
      }
      extractionStatus.value = 'mock_fallback'
      message.warning('网络请求失败，已使用模拟数据')
      options.onExtracted?.()
    } finally {
      sseLog(requestId, 'extractStructuredData:finally', { extracting: false })
      // 延迟 2.5 秒再隐藏提取状态，让用户看到完成状态
      setTimeout(() => {
        extracting.value = false
      }, 2500)
    }
  }

  return {
    extracting,
    extractionProgress,
    extractionStatus,
    extractStructuredData
  }
}
