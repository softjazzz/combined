/**
 * 统一数据验证工具
 * 提供可复用的验证规则和函数
 */

// 验证结果接口
export interface ValidationResult {
  isValid: boolean
  errors: string[]
  warnings?: string[]
}

// 通用验证规则
export class ValidationRules {
  
  // 必填验证
  static required(value: unknown, fieldName: string): string | null {
    if (value === null || value === undefined || value === '') {
      return `${fieldName}不能为空`
    }
    return null
  }

  // 字符串长度验证
  static stringLength(value: string, min: number, max: number, fieldName: string): string | null {
    if (!value) return null
    
    const length = value.trim().length
    if (length < min) {
      return `${fieldName}长度不能少于${min}个字符`
    }
    if (length > max) {
      return `${fieldName}长度不能超过${max}个字符`
    }
    return null
  }

  // 数字范围验证
  static numberRange(value: number, min: number, max: number, fieldName: string): string | null {
    if (value < min || value > max) {
      return `${fieldName}必须在${min}-${max}之间`
    }
    return null
  }

  // 邮箱验证
  static email(value: string): string | null {
    if (!value) return null
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(value)) {
      return '请输入有效的邮箱地址'
    }
    return null
  }

  // 手机号验证
  static phone(value: string): string | null {
    if (!value) return null
    
    const phoneRegex = /^1[3-9]\d{9}$/
    if (!phoneRegex.test(value)) {
      return '请输入有效的手机号码'
    }
    return null
  }

  // 身份证验证
  static idCard(value: string): string | null {
    if (!value) return null
    
    const idCardRegex = /^[1-9]\d{5}(18|19|20)\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$/
    if (!idCardRegex.test(value)) {
      return '请输入有效的身份证号码'
    }
    return null
  }

  // 日期验证
  static date(value: string, fieldName: string): string | null {
    if (!value) return null
    
    const date = new Date(value)
    if (isNaN(date.getTime())) {
      return `${fieldName}格式不正确`
    }
    return null
  }

  // 日期范围验证
  static dateRange(value: string, minDate?: string, maxDate?: string, fieldName: string = '日期'): string | null {
    const dateError = this.date(value, fieldName)
    if (dateError) return dateError
    
    const date = new Date(value)
    
    if (minDate && date < new Date(minDate)) {
      return `${fieldName}不能早于${minDate}`
    }
    
    if (maxDate && date > new Date(maxDate)) {
      return `${fieldName}不能晚于${maxDate}`
    }
    
    return null
  }

  // 文件类型验证
  static fileType(file: File, allowedTypes: string[]): string | null {
    if (!allowedTypes.includes(file.type)) {
      return `不支持的文件格式，仅支持：${allowedTypes.join(', ')}`
    }
    return null
  }

  // 文件大小验证
  static fileSize(file: File, maxSizeInMB: number): string | null {
    const maxSizeInBytes = maxSizeInMB * 1024 * 1024
    if (file.size > maxSizeInBytes) {
      return `文件大小不能超过${maxSizeInMB}MB`
    }
    return null
  }

  // 医疗相关验证
  static patientName(value: string): string | null {
    if (!value) return '患者姓名不能为空'
    
    const nameRegex = /^[\u4e00-\u9fa5a-zA-Z\s]{2,20}$/
    if (!nameRegex.test(value.trim())) {
      return '患者姓名格式不正确，仅支持中文、英文和空格，长度2-20个字符'
    }
    return null
  }

  static patientAge(value: number): string | null {
    if (value === null || value === undefined) return '患者年龄不能为空'
    return this.numberRange(value, 0, 150, '患者年龄')
  }

  static department(value: string): string | null {
    if (!value) return '科室不能为空'
    
    const validDepartments = [
      '内科', '外科', '妇产科', '儿科', '眼科', '耳鼻喉科', 
      '皮肤科', '神经科', '精神科', '急诊科', '麻醉科', '影像科',
      '心内科', '心外科', '胸外科', '神经外科', '泌尿外科', 
      '骨科', '呼吸内科', '消化内科', '肾内科', '血液科', '肿瘤科'
    ]
    
    if (!validDepartments.includes(value)) {
      return '请选择有效的科室'
    }
    return null
  }

  static medicalContent(value: string): string | null {
    if (!value) return '病案内容不能为空'
    
    const content = value.trim()
    if (content.length < 50) {
      return '病案内容至少需要50个字符'
    }
    if (content.length > 10000) {
      return '病案内容不能超过10000个字符'
    }
    return null
  }
}

// 表单验证器类
export class FormValidator {
  private errors: Record<string, string[]> = {}
  private warnings: Record<string, string[]> = {}

  // 添加验证规则
  validate(field: string, value: unknown,  rules: ((value: unknown) => string | null)[]): this {
    this.errors[field] = []
    this.warnings[field] = []

    for (const rule of rules) {
      const error = rule(value)
      if (error) {
        this.errors[field].push(error)
      }
    }

    return this
  }

  // 添加警告
  warn(field: string, message: string): this {
    if (!this.warnings[field]) {
      this.warnings[field] = []
    }
    this.warnings[field].push(message)
    return this
  }

  // 获取验证结果
  getResult(): ValidationResult {
    const hasErrors = Object.values(this.errors).some(errors => errors.length > 0)
    const allErrors = Object.values(this.errors).flat()
    const allWarnings = Object.values(this.warnings).flat()

    return {
      isValid: !hasErrors,
      errors: allErrors,
      warnings: allWarnings.length > 0 ? allWarnings : undefined
    }
  }

  // 获取字段错误
  getFieldErrors(field: string): string[] {
    return this.errors[field] || []
  }

  // 获取字段警告
  getFieldWarnings(field: string): string[] {
    return this.warnings[field] || []
  }

  // 清空验证结果
  clear(): this {
    this.errors = {}
    this.warnings = {}
    return this
  }
}

// 医疗记录验证器
export function validateMedicalRecord(data): ValidationResult {
  const validator = new FormValidator()

  validator
    .validate('patient_name', data.patient_name, [
      ValidationRules.patientName
    ])
    .validate('patient_age', data.patient_age, [
      ValidationRules.patientAge
    ])
    .validate('patient_gender', data.patient_gender, [
      (value) => ValidationRules.required(value, '患者性别')
    ])
    .validate('department', data.department, [
      ValidationRules.department
    ])
    .validate('admission_date', data.admission_date, [
      (value) => ValidationRules.required(value, '入院日期'),
      (value) => ValidationRules.dateRange(value, '1900-01-01', new Date().toISOString().split('T')[0], '入院日期')
    ])
    .validate('content', data.content, [
      ValidationRules.medicalContent
    ])

  // 文件验证（如果有）
  if (data.file) {
    const allowedTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]

    validator.validate('file', data.file, [
      (file) => ValidationRules.fileType(file, allowedTypes),
      (file) => ValidationRules.fileSize(file, 10)
    ])
  }

  return validator.getResult()
}

// Ant Design Vue 表单规则转换器
export function toAntdRules(validators: ((value: unknown) => string | null)[]): unknown[] {
  return validators.map(validator => ({
    validator: (_rule: unknown,  value: unknown) => {
      const error = validator(value)
      if (error) {
        return Promise.reject(new Error(error))
      }
      return Promise.resolve()
    }
  }))
}

// 常用的 Ant Design Vue 验证规则
export const AntdValidationRules = {
  patientName: toAntdRules([ValidationRules.patientName]),
  patientAge: toAntdRules([ValidationRules.patientAge]),
  department: toAntdRules([ValidationRules.department]),
  medicalContent: toAntdRules([ValidationRules.medicalContent]),
  email: toAntdRules([ValidationRules.email]),
  phone: toAntdRules([ValidationRules.phone]),
  required: (fieldName: string) => toAntdRules([(value) => ValidationRules.required(value, fieldName)])
} 