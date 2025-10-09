import { describe, it, expect } from 'vitest'
import {
  ValidationRules,
  FormValidator,
  validateMedicalRecord,
  toAntdRules
} from '@/utils/validation'

describe('ValidationRules', () => {
  it('validates required fields', () => {
    expect(ValidationRules.required('', '字段')).toBe('字段不能为空')
    expect(ValidationRules.required(null, '字段')).toBe('字段不能为空')
    expect(ValidationRules.required('value', '字段')).toBeNull()
  })

  it('enforces string length boundaries', () => {
    expect(ValidationRules.stringLength('abc', 5, 10, '名称')).toBe('名称长度不能少于5个字符')
    expect(ValidationRules.stringLength('a'.repeat(11), 1, 10, '名称')).toBe('名称长度不能超过10个字符')
    expect(ValidationRules.stringLength('valid', 1, 10, '名称')).toBeNull()
  })

  it('checks number ranges', () => {
    expect(ValidationRules.numberRange(5, 10, 20, '分值')).toBe('分值必须在10-20之间')
    expect(ValidationRules.numberRange(15, 10, 20, '分值')).toBeNull()
  })

  it('validates contact information', () => {
    expect(ValidationRules.email('invalid')).toBe('请输入有效的邮箱地址')
    expect(ValidationRules.email('user@example.com')).toBeNull()

    expect(ValidationRules.phone('123456')).toBe('请输入有效的手机号码')
    expect(ValidationRules.phone('13812345678')).toBeNull()
  })

  it('validates healthcare-specific fields', () => {
    expect(ValidationRules.patientName('张三')).toBeNull()
    expect(ValidationRules.patientName('')).toBe('患者姓名不能为空')
    expect(ValidationRules.patientName('a')).toBe('患者姓名格式不正确，仅支持中文、英文和空格，长度2-20个字符')

    expect(ValidationRules.patientAge(200)).toBe('患者年龄必须在0-150之间')
    expect(ValidationRules.patientAge(30)).toBeNull()

    expect(ValidationRules.department('内科')).toBeNull()
    expect(ValidationRules.department('未知科室')).toBe('请选择有效的科室')
  })

  it('validates file metadata', () => {
    const validFile = { type: 'application/pdf', size: 2 * 1024 * 1024 } as File
    const invalidTypeFile = { type: 'image/png', size: 1024 } as File
    const oversizedFile = { type: 'application/pdf', size: 15 * 1024 * 1024 } as File

    const allowedTypes = ['text/plain', 'application/pdf']

    expect(ValidationRules.fileType(validFile, allowedTypes)).toBeNull()
    expect(ValidationRules.fileType(invalidTypeFile, allowedTypes)).toBe(
      '不支持的文件格式，仅支持：text/plain, application/pdf'
    )

    expect(ValidationRules.fileSize(validFile, 5)).toBeNull()
    expect(ValidationRules.fileSize(oversizedFile, 5)).toBe('文件大小不能超过5MB')
  })
})

describe('FormValidator', () => {
  it('collects errors and warnings', () => {
    const validator = new FormValidator()
    validator
      .validate('name', '', [
        value => ValidationRules.required(value, '姓名'),
        value => ValidationRules.stringLength(value as string, 2, 5, '姓名')
      ])
      .warn('name', '姓名格式需要人工复核')

    const result = validator.getResult()
    expect(result.isValid).toBe(false)
    expect(result.errors).toContain('姓名不能为空')
    expect(result.errors).toContain('姓名长度不能少于2个字符')
    expect(result.warnings).toContain('姓名格式需要人工复核')
    expect(validator.getFieldErrors('name')).toHaveLength(2)
    expect(validator.getFieldWarnings('name')).toHaveLength(1)
  })

  it('clears aggregated results', () => {
    const validator = new FormValidator()
    validator.validate('field', '', [value => ValidationRules.required(value, '字段')])
    expect(validator.getResult().isValid).toBe(false)

    validator.clear()
    expect(validator.getResult().isValid).toBe(true)
    expect(validator.getResult().errors).toHaveLength(0)
  })
})

describe('validateMedicalRecord', () => {
  it('returns valid result for complete payload', () => {
    const result = validateMedicalRecord({
      patient_name: '张三',
      patient_age: 35,
      patient_gender: '男',
      department: '内科',
      admission_date: '2024-01-01',
      content: '病案内容'.padEnd(60, '。'),
      file: { type: 'application/pdf', size: 1 * 1024 * 1024 }
    })

    expect(result.isValid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('reports missing or invalid fields', () => {
    const result = validateMedicalRecord({
      patient_name: '',
      patient_age: 200,
      patient_gender: '',
      department: '未知科室',
      admission_date: 'not-a-date',
      content: '过短',
      file: { type: 'image/png', size: 20 * 1024 * 1024 }
    })

    expect(result.isValid).toBe(false)
    expect(result.errors).toEqual(
      expect.arrayContaining([
        '患者姓名不能为空',
        '患者年龄必须在0-150之间',
        '患者性别不能为空',
        '请选择有效的科室',
        '入院日期格式不正确',
        '病案内容至少需要50个字符',
        '不支持的文件格式，仅支持：text/plain, application/pdf, application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '文件大小不能超过10MB'
      ])
    )
  })
})

describe('toAntdRules', () => {
  it('wraps rules into promise-based validators', async () => {
    const rules = toAntdRules([value => ValidationRules.required(value, '名称')])
    const rule = rules[0] as { validator: (_rule: unknown, value: unknown) => Promise<void> }

    await expect(rule.validator({}, '有效值')).resolves.toBeUndefined()
    await expect(rule.validator({}, '')).rejects.toHaveProperty('message', '名称不能为空')
  })
})
