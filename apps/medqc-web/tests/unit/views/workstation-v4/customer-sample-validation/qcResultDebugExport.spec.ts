import { describe, expect, it, vi } from 'vitest'

import {
  buildQcResultDebugText,
  copyQcResultDebugText,
} from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'

describe('qcResultDebugExport', () => {
  it('exports redacted conclusion, controlled facts, criteria, data gaps and evidence without reinterpreting them', () => {
    const result = buildQcResultDebugText(
      [
        {
          rule_id: 'LX0609-011',
          rule_name: 'CT/MRI 报告后病程记录',
          status: 'data_gap',
          display_status: '数据不足',
          reason_code: 'required_time_unavailable',
          conclusion: '缺少可用于时序核对的病程记录时间。',
          customer_display_facts: { report_time: '2026-08-19 10:00:00' },
          criterion_results: [
            {
              criterion_id: 'time_window',
              kind: 'date_interval',
              status: 'unknown',
              reason_code: 'required_time_unavailable',
            },
          ],
          data_gap_details: { missing_fields: ['daily_course_record.record_time'] },
          evidence: [
            {
              source_ref: 'exam-safe-1',
              source_type: 'exam_master',
              source_label: 'CT检查主记录',
              record_time: '2026-08-19 10:00:00',
              field_path: 'exam_master.report_time',
              evidence_excerpt: '腹部CT检查完成。',
              excerpt_kind: '字段级依据',
            },
          ],
        },
      ],
      {
        instituteId: 'H1',
        patientId: 'P001',
        visitId: 'V001',
        patientName: '周勇书',
        recordRef: 'record-safe-1',
        jobId: 'job-safe-1',
        ruleSetKey: 'luxian_0609_qc_v1',
        ruleSetVersion: '2026.08.27',
        resultSchemaVersion: 'lx0609-single-record-result-v1',
        expectedRuleCount: 75,
        resultRuleCount: 75,
        isComplete: true,
      },
    )

    expect(result).toContain('格式版本：medqc-qc-debug-v4-redacted-minimal')
    expect(result).toContain('内容已脱敏')
    expect(result).toContain('机构ID：机构-001')
    expect(result).toContain('患者ID：患者-001')
    expect(result).toContain('就诊ID：就诊-001')
    expect(result).toContain('质控任务ID：任务-001')
    expect(result).toContain('规则集版本：2026.08.27')
    expect(result).toContain('结果完整性：完整')
    expect(result).toContain('- data_gap：1')
    expect(result).toContain('LX0609-011 CT/MRI 报告后病程记录')
    expect(result).toContain('原始状态：data_gap')
    expect(result).toContain('原因码：required_time_unavailable')
    expect(result).toContain('质控结论：缺少可用于时序核对的病程记录时间。')
    expect(result).toContain('受控判定事实 customer_display_facts')
    expect(result).toContain('daily_course_record.record_time')
    expect(result).toContain('关键证据 evidence（1 条）')
    expect(result).toContain('安全引用：引用-001')
    expect(result).toContain('字段路径：exam_master.report_time')
    expect(result).toContain('关键原文摘要：腹部CT检查完成。')
  })

  it('redacts patient names inside narrative text and common direct identifiers', () => {
    const result = buildQcResultDebugText(
      [
        {
          rule_id: 'LX0609-018',
          rule_name: '主诉与第一诊断',
          status: 'non_compliant',
          conclusion:
            '患者周勇书，男，住址：四川省泸县某镇1组，联系电话13800138000，身份证号510000199001011234。',
          detail:
            '患者周勇书,性别男，于2026-07-07 19:00:01入院。医师签名：张云海。文件位于D:\\medqc\\secret.json。',
          customer_display_facts: {
            patient_id: '0000176759',
            visit_id: '2563837',
            source_document_ids: ['5038135||14'],
            admission_time: '2026-07-07 19:00:01',
          },
          evidence: [
            {
              source_ref: 'document:5038135||14',
              source_type: 'first_course_record',
              source_label: '首次病程记录',
              record_time: '2026-07-07 19:39:10',
              field_path: 'first_course_record.record_content',
              evidence_excerpt: '患者周勇书，男，联系电话13800138000。',
              excerpt_kind: '字段级依据',
            },
          ],
        },
      ],
      {
        instituteId: 'HOSPITAL-01',
        patientId: '0000176759',
        visitId: '2563837',
        patientName: '周勇书',
        recordId: '2563837',
        jobId: '18c48be4-4221-40d1-80a5-d1be30f7263e',
      },
    )

    expect(result).not.toContain('周勇书')
    expect(result).not.toContain('0000176759')
    expect(result).not.toContain('2563837')
    expect(result).not.toContain('5038135||14')
    expect(result).not.toContain('13800138000')
    expect(result).not.toContain('510000199001011234')
    expect(result).not.toContain('四川省泸县某镇1组')
    expect(result).not.toContain('张云海')
    expect(result).not.toContain('D:\\medqc\\secret.json')
    expect(result).not.toContain('2026-07-07')
    expect(result).toContain('患者A')
    expect(result).toContain('患者-001')
    expect(result).toContain('就诊-001')
    expect(result).toContain('文书-001')
    expect(result).toContain('[电话号码已脱敏]')
    expect(result).toContain('[身份证号已脱敏]')
    expect(result).toContain('住址：[地址已脱敏]')
    expect(result).toContain('医师签名：医务人员A')
    expect(result).toContain('[本地路径已脱敏]')
    expect(result).toContain('LX0609-018')
    expect(result).toContain('first_course_record.record_content')
    expect(result).toContain('non_compliant')
  })

  it('infers a patient name from a strongly labelled narrative when context has no name', () => {
    const result = buildQcResultDebugText([
      {
        rule_id: 'LX0609-006',
        rule_name: '上级医师查房记录',
        status: 'compliant',
        conclusion: '患者李庆珍,性别女,年龄89岁，已完成上级医师查房。',
      },
    ])

    expect(result).not.toContain('李庆珍')
    expect(result).toContain('患者A,性别女')
  })

  it('removes credentials, infrastructure details and full raw documents while retaining debug facts', () => {
    const result = buildQcResultDebugText([
      {
        rule_id: 'LX0609-020',
        rule_name: '会诊建议执行情况',
        status: 'data_gap',
        reason_code: 'consultation_evidence_missing',
        conclusion:
          '第2次会诊缺少执行证据，联系人：王小兰，电话0830-1234567。password=plain-secret; Cookie: session=another-secret',
        customer_display_facts: {
          consultation_id: 'CONSULT-2026-009',
          specimen_no: 'LAB-009',
          doctor_name: '胡强',
          record_content: '患者周勇书的完整病历正文不应进入调试剪贴板。',
          api_key: 'sk-proj-abcdefghijklmnopqrstuvwxyz',
          has_api_key: true,
          database_user: 'postgres',
          phone: 13800138000,
          headers: {
            authorization: 'Bearer secret-access-token-value',
            cookie: 'session=raw-cookie-value',
          },
          source_url: 'https://10.2.3.4:8001/api/v1/qc?token=secret',
          server_path: '\\\\medqc-server\\share\\patient.json',
          trace_path: '/var/log/medqc/patient.log',
        },
        evidence: [
          {
            source_ref: 'CONSULT-2026-009',
            source_type: 'consultation_record',
            source_label: '会诊记录单',
            record_time: '2026-08-19 10:07:00',
            field_path: 'consultation_record.record_content',
            evidence_excerpt: '会诊意见建议继续保肝治疗，已遵执行。',
            excerpt_kind: '字段级依据',
          },
        ],
      },
    ])

    expect(result).toContain('格式版本：medqc-qc-debug-v4-redacted-minimal')
    expect(result).toContain('LX0609-020')
    expect(result).toContain('consultation_evidence_missing')
    expect(result).toContain('consultation_record.record_content')
    expect(result).toContain('会诊意见建议继续保肝治疗，已遵执行。')
    expect(result).toContain('[完整原始正文已省略]')
    expect(result).toContain('[访问凭证已脱敏]')
    expect(result).toContain('"has_api_key": true')
    expect(result).toContain('[网络地址已脱敏]')
    expect(result).toContain('[本地路径已脱敏]')
    expect(result).toContain('[关联人员已脱敏]')
    expect(result).toContain('医务人员A')
    expect(result).toContain('标识-001')
    expect(result).not.toContain('周勇书')
    expect(result).not.toContain('胡强')
    expect(result).not.toContain('王小兰')
    expect(result).not.toContain('0830-1234567')
    expect(result).not.toContain('sk-proj-abcdefghijklmnopqrstuvwxyz')
    expect(result).not.toContain('secret-access-token-value')
    expect(result).not.toContain('raw-cookie-value')
    expect(result).not.toContain('plain-secret')
    expect(result).not.toContain('another-secret')
    expect(result).not.toContain('postgres')
    expect(result).not.toContain('13800138000')
    expect(result).not.toContain('LAB-009')
    expect(result).not.toContain('10.2.3.4')
    expect(result).not.toContain('medqc-server')
    expect(result).not.toContain('/var/log/medqc')
    expect(result).not.toContain('完整病历正文不应进入')
  })

  it('copies the generated text through the browser clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    await expect(copyQcResultDebugText('调试内容')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('调试内容')
  })
})
