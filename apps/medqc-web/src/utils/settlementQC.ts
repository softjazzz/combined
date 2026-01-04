/**
 * 医保结算清单质控规则引擎
 * Settlement Form QC Validation Engine
 * 
 * 基于《四川省医疗保障基金结算清单质控规则》(2025年9月3日版)
 * 规则分类：
 *   - 事前规则 (40条)：上传前必须通过
 *   - 事后规则 (86条)：用于数据筛查
 * 规则类型：
 *   - 强制 (34条)：必须符合
 *   - 严重 (27条)：红色提示，影响分组
 *   - 提示 (62条)：绿色提示，规范性
 */

import type {
    SettlementForm,
    SettlementQCReport,
    QCValidationResult,
    SettlementBasicInfo,
    SettlementInpatientInfo,
    SettlementFeeInfo
} from '@/types/settlement'

// ==================== 规则定义 ====================

export interface QCRule {
    id: string                    // 规则ID (对应四川省规则编号)
    field: string                 // 字段名称
    ruleName: string              // 规则名称
    description: string           // 规则描述
    auditLogic: string            // 审核逻辑
    severity: 'error' | 'warning' | 'info'  // error=强制/严重, warning=提示
    category: 'required' | 'format' | 'logic' | 'consistency'
    isPreEvent: boolean           // true=事前规则, false=事后规则
    validate: (form: SettlementForm, context?: QCContext) => boolean
    getMessage: (form: SettlementForm) => string
}

export interface QCContext {
    admissionTime?: Date | null
    dischargeTime?: Date | null
    birthDate?: Date | null
}

// ==================== 校验辅助函数 ====================

/** 检查字符串是否非空 */
const isNotEmpty = (value: string | null | undefined): boolean => {
    return value !== null && value !== undefined && value.trim() !== ''
}

/** 检查数字是否有效 */
const isValidNumber = (value: number | null | undefined): boolean => {
    return value !== null && value !== undefined && !isNaN(value)
}

/** 校验 ICD-10 编码格式 (医保2.0版 A00-Z99.xxx) */
const isValidICD10 = (code: string): boolean => {
    if (!code) return false
    // ICD-10 格式：字母开头 + 2位数字 + 可选小数点 + 可选数字
    // 排除 V/W/X/Y 开头的外因编码
    const pattern = /^[A-UZ]\d{2}(\.\d{1,4})?$/i
    return pattern.test(code.trim())
}

/** 校验 ICD-9-CM-3 手术编码格式 (医保2.0版 00.00-99.99) */
const isValidICD9CM3 = (code: string): boolean => {
    if (!code) return false
    const pattern = /^\d{2}\.\d{2,4}$/
    return pattern.test(code.trim())
}

/** 校验身份证号码格式 (18位) */
const isValidIDCard = (idCard: string): boolean => {
    if (!idCard) return false
    const pattern = /^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$/
    return pattern.test(idCard.trim())
}

/** 校验邮编格式 (6位数字) */
const isValidPostcode = (code: string): boolean => {
    if (!code) return false
    return /^\d{6}$/.test(code.trim())
}

/** 校验诊断编码范围 (A-U和Z开头，不包括V/W/X/Y) */
const isValidDiagnosisCodeRange = (code: string): boolean => {
    if (!code) return true
    const firstChar = code.trim().charAt(0).toUpperCase()
    return !['V', 'W', 'X', 'Y'].includes(firstChar)
}

/** 检查是否为医保停用码 (简化实现，实际需对接医保码库) */
const isDisabledCode = (_code: string): boolean => {
    // TODO: 对接医保2.0版ICD编码库
    return false
}

/** 计算年龄是否与诊断匹配 */
const isAgeMatchForNewborn = (ageInDays: number | null, code: string): boolean => {
    if (!code) return true
    // P10-P15 为新生儿产伤相关编码，需要天龄 < 365
    if (/^P1[0-5]/.test(code) && ageInDays !== null) {
        return ageInDays < 365
    }
    return true
}

// ==================== 四川省质控规则库 ====================

export const QC_RULES: QCRule[] = [
    // ========================================================================
    // 事前规则 - 强制 (必须在上传前通过)
    // ========================================================================

    // --- 规则1: 病案号非空性 ---
    {
        id: 'SC001',
        field: '病案号',
        ruleName: '病案号非空性',
        description: '定点医疗机构为每一位患者病案设置的唯一编码',
        auditLogic: '审核病案号是否为空，若为空则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.basicInfo.caseNumber),
        getMessage: () => '病案号不能为空'
    },

    // --- 规则2: 年龄(天)非空性 ---
    {
        id: 'SC002',
        field: '年龄(天)',
        ruleName: '年龄(天)非空性',
        description: '当年龄(岁)为空时，年龄(天)必须填写',
        auditLogic: '当年龄(岁)为空时，判断年龄(天)是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            if (form.basicInfo.age === null || form.basicInfo.age === undefined) {
                return isValidNumber(form.basicInfo.ageInDays)
            }
            return true
        },
        getMessage: () => '年龄(岁)为空时，年龄(天)必须填写'
    },

    // --- 规则4: 年龄(岁)(天)互斥性 ---
    {
        id: 'SC004',
        field: '年龄',
        ruleName: '年龄(岁)(天)互斥性',
        description: '年龄岁和天字段不能同时有值',
        auditLogic: '审核年龄(岁)(天)两个字段不能同时存在',
        severity: 'error',
        category: 'logic',
        isPreEvent: true,
        validate: (form) => {
            const hasAge = isValidNumber(form.basicInfo.age)
            const hasAgeInDays = isValidNumber(form.basicInfo.ageInDays)
            return !(hasAge && hasAgeInDays)
        },
        getMessage: () => '年龄(岁)和年龄(天)不能同时填写'
    },

    // --- 规则5: 国籍非空性 ---
    {
        id: 'SC005',
        field: '国籍',
        ruleName: '国籍非空性',
        description: '患者所属国籍，按照GB/T 2659-2000标准填写',
        auditLogic: '审核国籍是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.basicInfo.nationality),
        getMessage: () => '国籍不能为空'
    },

    // --- 规则7: 职业非空性 ---
    {
        id: 'SC007',
        field: '职业',
        ruleName: '职业非空性',
        description: '患者当前从事的职业类别，按照GB/T2261.4-2003标准填写',
        auditLogic: '审核职业是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.basicInfo.occupation),
        getMessage: () => '职业不能为空'
    },

    // --- 规则20: 新生儿出生体重非空值 ---
    {
        id: 'SC020',
        field: '新生儿出生体重',
        ruleName: '新生儿出生体重非空值',
        description: '新生儿(天龄<29天)入院时，出生体重必须填写',
        auditLogic: '新生儿(天龄小于29天)入院时，新生儿出生体重必须填写',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const ageInDays = form.basicInfo.ageInDays
            if (ageInDays !== null && ageInDays !== undefined && ageInDays < 29) {
                return isValidNumber(form.basicInfo.newbornBirthWeight)
            }
            return true
        },
        getMessage: () => '新生儿(天龄<29天)入院时，出生体重必须填写'
    },

    // --- 规则24: 新生儿入院体重非空值 ---
    {
        id: 'SC024',
        field: '新生儿入院体重',
        ruleName: '新生儿入院体重非空值',
        description: '新生儿(天龄<29天)入院时，入院体重必须填写',
        auditLogic: '新生儿(天龄小于29天)入院时，新生儿入院体重必须填写',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const ageInDays = form.basicInfo.ageInDays
            if (ageInDays !== null && ageInDays !== undefined && ageInDays < 29) {
                return isValidNumber(form.basicInfo.newbornAdmissionWeight)
            }
            return true
        },
        getMessage: () => '新生儿(天龄<29天)入院时，入院体重必须填写'
    },

    // --- 规则31: 入院时间非空性 ---
    {
        id: 'SC031',
        field: '入院时间',
        ruleName: '入院时间非空性',
        description: '患者办理入院手续后实际入住病房的时间',
        auditLogic: '审核入院时间是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.inpatientInfo?.admissionTime),
        getMessage: () => '入院时间不能为空'
    },

    // --- 规则32: 入院时间合理性 ---
    {
        id: 'SC032',
        field: '入院时间',
        ruleName: '入院时间合理性',
        description: '入院时间应小于出院时间',
        auditLogic: '审核入院时间是否小于出院时间，若否则不通过',
        severity: 'error',
        category: 'consistency',
        isPreEvent: true,
        validate: (form, context) => {
            if (!context?.admissionTime || !context?.dischargeTime) return true
            return context.admissionTime < context.dischargeTime
        },
        getMessage: () => '入院时间应早于出院时间'
    },

    // --- 规则34: 出院时间非空性 ---
    {
        id: 'SC034',
        field: '出院时间',
        ruleName: '出院时间非空性',
        description: '患者实际办理出院手续时的时间',
        auditLogic: '审核出院时间是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.inpatientInfo?.dischargeTime),
        getMessage: () => '出院时间不能为空'
    },

    // --- 规则35: 出院时间合理性 ---
    {
        id: 'SC035',
        field: '出院时间',
        ruleName: '出院时间合理性',
        description: '出院时间应大于入院时间',
        auditLogic: '审核出院时间是否大于入院时间，若否则不通过',
        severity: 'error',
        category: 'consistency',
        isPreEvent: true,
        validate: (form, context) => {
            if (!context?.admissionTime || !context?.dischargeTime) return true
            return context.dischargeTime > context.admissionTime
        },
        getMessage: () => '出院时间应晚于入院时间'
    },

    // --- 规则46: 出院西医主要诊断名称与代码非空性 ---
    {
        id: 'SC046',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断名称与代码非空性',
        description: '主诊断名称和代码必须填写',
        auditLogic: '审核出院西医主要诊断名称与代码是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            return isNotEmpty(primaryDx?.westDiagnosis) && isNotEmpty(primaryDx?.westCode)
        },
        getMessage: () => '出院主诊断名称和代码不能为空'
    },

    // --- 规则47: 出院西医主要诊断名称与代码规范性 ---
    {
        id: 'SC047',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断名称与代码规范性',
        description: '主诊断应按照医保2.0版ICD-10标准填写',
        auditLogic: '审核主诊断编码是否符合医保2.0版ICD-10标准',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!primaryDx?.westCode) return true
            return isValidICD10(primaryDx.westCode)
        },
        getMessage: () => '主诊断编码格式不正确（应为ICD-10格式）'
    },

    // --- 规则48: 诊断编码中存在医保停用码 ---
    {
        id: 'SC048',
        field: '出院主诊断',
        ruleName: '诊断编码中存在医保停用码',
        description: '诊断编码不能使用医保停用码',
        auditLogic: '检查诊断编码是否为医保停用码',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!primaryDx?.westCode) return true
            return !isDisabledCode(primaryDx.westCode)
        },
        getMessage: () => '主诊断编码为医保停用码'
    },

    // --- 规则49: 缺少主诊断 ---
    {
        id: 'SC049',
        field: '出院主诊断',
        ruleName: '缺少主诊断',
        description: '必须有一个主诊断',
        auditLogic: '是否有主诊断打标为"1"，是则通过，否则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            return isNotEmpty(primaryDx?.westCode) || isNotEmpty(primaryDx?.westDiagnosis)
        },
        getMessage: () => '缺少主诊断'
    },

    // --- 规则60: 主诊断重复 ---
    {
        id: 'SC060',
        field: '出院诊断',
        ruleName: '主诊断重复',
        description: '主诊断标识不能存在2个及以上',
        auditLogic: '是否存在多个主诊断标识为"1"的诊断，若是则不通过',
        severity: 'error',
        category: 'consistency',
        isPreEvent: true,
        validate: (_form) => {
            // 当前表单结构中，第一行即为主诊断，不存在重复问题
            return true
        },
        getMessage: () => '存在多个主诊断'
    },

    // --- 规则61: 出院西医其他诊断规范性 ---
    {
        id: 'SC061',
        field: '出院其他诊断',
        ruleName: '出院西医其他诊断名称与代码规范性',
        description: '其他诊断应按照医保2.0版ICD-10标准填写',
        auditLogic: '审核其他诊断编码是否符合医保2.0版ICD-10标准',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            for (let i = 1; i < diagRows.length; i++) {
                if (diagRows[i].westCode && !isValidICD10(diagRows[i].westCode)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '其他诊断编码格式不正确（应为ICD-10格式）'
    },

    // --- 规则67: 出院诊断编码重复 ---
    {
        id: 'SC067',
        field: '出院诊断',
        ruleName: '出院诊断编码重复',
        description: '诊断编码之间不能有重复',
        auditLogic: '审核出院诊断编码之间是否有重复编码，若是则不通过',
        severity: 'error',
        category: 'consistency',
        isPreEvent: true,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            const codes = diagRows.map(d => d.westCode).filter(Boolean)
            const uniqueCodes = new Set(codes)
            return codes.length === uniqueCodes.size
        },
        getMessage: () => '存在重复的诊断编码'
    },

    // --- 规则72: 主要手术及操作规范性 ---
    {
        id: 'SC072',
        field: '主手术',
        ruleName: '主要手术及操作名称与代码规范性',
        description: '主手术应按照ICD-9-CM-3医保2.0版标准填写',
        auditLogic: '审核主手术编码是否符合ICD-9-CM-3医保2.0版标准',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const primaryOp = form.inpatientInfo?.surgeryRows?.[0]
            if (!primaryOp?.code) return true
            return isValidICD9CM3(primaryOp.code)
        },
        getMessage: () => '主手术编码格式不正确（应为ICD-9-CM-3格式）'
    },

    // --- 规则76: 其他手术及操作规范性 ---
    {
        id: 'SC076',
        field: '其他手术',
        ruleName: '其他手术及操作名称与代码规范性',
        description: '其他手术应按照ICD-9-CM-3医保2.0版标准填写',
        auditLogic: '审核其他手术编码是否符合ICD-9-CM-3医保2.0版标准',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            for (let i = 1; i < opRows.length; i++) {
                if (opRows[i].code && !isValidICD9CM3(opRows[i].code)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '其他手术编码格式不正确（应为ICD-9-CM-3格式）'
    },

    // --- 规则85: 术者医师姓名合理性 ---
    {
        id: 'SC085',
        field: '术者医师',
        ruleName: '术者医师姓名合理性',
        description: '当有手术操作时，须有术者医师姓名',
        auditLogic: '当患者有手术及操作时，审核是否有术者医师姓名',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            const hasOperation = opRows.some(op => isNotEmpty(op.code))
            if (hasOperation) {
                return opRows.some(op => op.code && isNotEmpty(op.surgeonName))
            }
            return true
        },
        getMessage: () => '有手术操作时，术者医师姓名不能为空'
    },

    // --- 规则109: 离院方式非空性 ---
    {
        id: 'SC109',
        field: '离院方式',
        ruleName: '离院方式非空性',
        description: '患者本次住院离开医院的方式',
        auditLogic: '审核离院方式是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isValidNumber(form.inpatientInfo?.dischargeMethod),
        getMessage: () => '离院方式不能为空'
    },

    // --- 规则110: 离院方式规范性 ---
    {
        id: 'SC110',
        field: '离院方式',
        ruleName: '离院方式规范性',
        description: '离院方式应为标准代码1-5或9',
        auditLogic: '审核离院方式是否为1-5或9中的任一项',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const method = form.inpatientInfo?.dischargeMethod
            if (method === null || method === undefined) return true
            return [1, 2, 3, 4, 5, 9].includes(method)
        },
        getMessage: () => '离院方式代码不正确（应为1-5或9）'
    },

    // --- 规则116: 主诊医师代码规范性 ---
    {
        id: 'SC116',
        field: '主诊医师',
        ruleName: '主诊医师代码规范性',
        description: '主诊医师代码应与医保平台编码匹配',
        auditLogic: '审核主诊医师代码是否与姓名相匹配',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const name = form.inpatientInfo?.attendingPhysicianName
            const code = form.inpatientInfo?.attendingPhysicianCode
            if (isNotEmpty(name)) {
                return isNotEmpty(code)
            }
            return true
        },
        getMessage: () => '主诊医师有姓名时，代码不能为空'
    },

    // --- 规则120: 业务流水号非空性 ---
    {
        id: 'SC120',
        field: '业务流水号',
        ruleName: '业务流水号非空性',
        description: '医疗卫生机构收费系统自动生成的流水号码',
        auditLogic: '审核业务流水号是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.feeInfo?.businessSerialNumber),
        getMessage: () => '业务流水号不能为空'
    },

    // --- 规则121: 票据代码非空性 ---
    {
        id: 'SC121',
        field: '票据代码',
        ruleName: '票据代码非空性',
        description: '医疗收费电子票据上的票据代码',
        auditLogic: '审核票据代码是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.feeInfo?.invoiceCode),
        getMessage: () => '票据代码不能为空'
    },

    // --- 规则122: 票据号码非空性 ---
    {
        id: 'SC122',
        field: '票据号码',
        ruleName: '票据号码非空性',
        description: '票据流水号',
        auditLogic: '审核票据号码是否为空，若是则不通过',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => isNotEmpty(form.feeInfo?.invoiceNumber),
        getMessage: () => '票据号码不能为空'
    },

    // ========================================================================
    // 事后规则 - 严重 (红色提示，影响分组)
    // ========================================================================

    // --- 规则38: 手术与住院天数不符 ---
    {
        id: 'SC038',
        field: '住院天数',
        ruleName: '手术与住院天数不符',
        description: '手术相关住院天数应与实际住院天数一致',
        auditLogic: '检查手术中住院天数相关手术是否与上传住院天数不符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要手术与住院天数关联表
            return true
        },
        getMessage: () => '手术与住院天数不符'
    },

    // --- 规则50: 出院西医主要诊断与患者性别不符 ---
    {
        id: 'SC050',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断与患者性别不符',
        description: '诊断应与患者性别相符',
        auditLogic: '审核出院西医主要诊断是否与患者性别相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const gender = form.basicInfo.gender
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!primaryDx?.westCode || !gender) return true

            const code = primaryDx.westCode.toUpperCase()
            // 男性不能有妇产科诊断 (O00-O99, N70-N98)
            if (gender === 1) {
                if (/^O/.test(code)) return false
                if (/^N[78]\d|^N9[0-8]/.test(code)) return false
            }
            // 女性不能有男性特有诊断 (N40-N51)
            if (gender === 2) {
                if (/^N4\d|^N5[01]/.test(code)) return false
            }
            return true
        },
        getMessage: () => '主诊断与患者性别不符'
    },

    // --- 规则51: 出院西医主要诊断与患者年龄不符 ---
    {
        id: 'SC051',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断与患者年龄不符',
        description: '诊断应与患者年龄相符',
        auditLogic: '审核出院西医主要诊断是否与患者年龄相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const age = form.basicInfo.age
            const ageInDays = form.basicInfo.ageInDays
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!primaryDx?.westCode) return true

            const code = primaryDx.westCode.toUpperCase()
            // P00-P96 新生儿疾病需要年龄<1岁或天龄<365天
            if (/^P/.test(code)) {
                if (age !== null && age >= 1) return false
                if (ageInDays !== null && ageInDays >= 365) return false
            }
            return true
        },
        getMessage: () => '主诊断与患者年龄不符'
    },

    // --- 规则52: 出院西医主要诊断与患者离院方式不符 ---
    {
        id: 'SC052',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断与患者离院方式不符',
        description: '死亡相关诊断的离院方式应为死亡',
        auditLogic: '审核诊断与死亡相关时离院方式是否相符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            const dischargeMethod = form.inpatientInfo?.dischargeMethod
            if (!primaryDx?.westCode || !dischargeMethod) return true

            // 死亡相关诊断 (简化判断)
            const code = primaryDx.westCode.toUpperCase()
            const isDeathDiagnosis = /^R99|^I46\.1/.test(code)

            if (isDeathDiagnosis && dischargeMethod !== 5) {
                return false
            }
            return true
        },
        getMessage: () => '死亡相关诊断的离院方式应为"死亡"'
    },

    // --- 规则55: 诊断冲突 ---
    {
        id: 'SC055',
        field: '出院诊断',
        ruleName: '诊断冲突',
        description: '诊断之间不应存在内涵矛盾',
        auditLogic: '检查主诊断和次要诊断是否存在冲突',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要诊断冲突关系表
            return true
        },
        getMessage: () => '存在诊断冲突'
    },

    // --- 规则57: 出院诊断缺少分娩结局相关诊断 ---
    {
        id: 'SC057',
        field: '出院诊断',
        ruleName: '出院诊断缺少分娩结局相关诊断',
        description: '分娩相关诊断需要有Z37分娩结局编码',
        auditLogic: '当有分娩诊断(O80-O84)时，必须有分娩结局(Z37)',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            const codes = diagRows.map(d => d.westCode?.toUpperCase()).filter(Boolean)

            // 检查是否有分娩诊断 O80-O84
            const hasDelivery = codes.some(c => /^O8[0-4]/.test(c || ''))
            // 检查是否有流产诊断 O00-O08
            const hasAbortion = codes.some(c => /^O0[0-8]/.test(c || ''))
            // 检查是否有分娩结局 Z37
            const hasOutcome = codes.some(c => /^Z37/.test(c || ''))

            if (hasDelivery && !hasAbortion && !hasOutcome) {
                return false
            }
            return true
        },
        getMessage: () => '分娩诊断缺少分娩结局编码(Z37)'
    },

    // --- 规则58: 诊断编码范围合理性 ---
    {
        id: 'SC058',
        field: '出院诊断',
        ruleName: '诊断编码范围合理性',
        description: '诊断编码应为A-U或Z开头，不包括V/W/X/Y',
        auditLogic: '诊断编码不应使用外因编码(V/W/X/Y开头)',
        severity: 'error',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            return diagRows.every(d => isValidDiagnosisCodeRange(d.westCode))
        },
        getMessage: () => '诊断编码不应使用外因编码(V/W/X/Y开头)'
    },

    // --- 规则74: 主要手术及操作与患者性别不符 ---
    {
        id: 'SC074',
        field: '主手术',
        ruleName: '主要手术及操作与患者性别不符',
        description: '手术应与患者性别相符',
        auditLogic: '审核主要手术及操作是否与患者性别相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const gender = form.basicInfo.gender
            const primaryOp = form.inpatientInfo?.surgeryRows?.[0]
            if (!primaryOp?.code || !gender) return true

            const code = primaryOp.code
            // 男性不能有妇产科手术 (68-75)
            if (gender === 1) {
                if (/^6[89]|^7[0-5]/.test(code)) return false
            }
            // 女性不能有男性特有手术 (60-64)
            if (gender === 2) {
                if (/^6[0-4]/.test(code)) return false
            }
            return true
        },
        getMessage: () => '主手术与患者性别不符'
    },

    // --- 规则111: 收费项目与离院方式不符 ---
    {
        id: 'SC111',
        field: '离院方式',
        ruleName: '收费项目与离院方式不符',
        description: '死亡相关收费项目的离院方式应为死亡',
        auditLogic: '检查死亡相关收费项目是否与离院方式不符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要收费明细数据
            return true
        },
        getMessage: () => '收费项目与离院方式不符'
    },

    // --- 规则53: 出院西医主要诊断选择错误(编码性) ---
    {
        id: 'SC053',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断选择错误(编码性)',
        description: '主诊断选择应正确',
        auditLogic: '审核出院西医主要诊断选择是否错误',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!primaryDx?.westCode) return true

            const code = primaryDx.westCode.toUpperCase()
            // Z码（健康状况因素）一般不应作为主诊断
            if (/^Z[0-9]{2}/.test(code) && !/^Z37|^Z38/.test(code)) {
                // 排除分娩结局Z37和活产婴儿Z38
                return false
            }
            return true
        },
        getMessage: () => '主诊断选择可能不当（Z码通常不作为主诊断）'
    },

    // --- 规则54: 出院西医主要诊断与新生儿出生体重不符 ---
    {
        id: 'SC054',
        field: '出院主诊断',
        ruleName: '出院西医主要诊断与新生儿出生体重不符',
        description: '新生儿体重相关诊断应与出生体重匹配',
        auditLogic: '当新生儿出生体重不为空时，审核主诊断是否相符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const birthWeight = form.basicInfo.newbornBirthWeight
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            if (!birthWeight || !primaryDx?.westCode) return true

            const code = primaryDx.westCode.toUpperCase()
            // 极低出生体重 P07.0 (体重<1000g)
            if (/^P07\.0/.test(code) && birthWeight >= 1000) return false
            // 低出生体重 P07.1 (体重1000-2499g)
            if (/^P07\.1/.test(code) && (birthWeight < 1000 || birthWeight >= 2500)) return false
            // 巨大儿 P08.0 (体重>=4000g)
            if (/^P08\.0/.test(code) && birthWeight < 4000) return false

            return true
        },
        getMessage: () => '主诊断与新生儿出生体重不符'
    },

    // --- 规则56: 联合诊断 ---
    {
        id: 'SC056',
        field: '出院诊断',
        ruleName: '联合诊断',
        description: '疾病伴合并症时应使用联合诊断编码',
        auditLogic: '检查是否应使用联合诊断编码',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            const codes = diagRows.map(d => d.westCode?.toUpperCase()).filter(Boolean)

            // 常见需要联合诊断的情况
            // 糖尿病(E10-E14)伴并发症应使用联合编码
            const hasDiabetes = codes.some(c => /^E1[0-4]/.test(c || ''))
            const hasDiabeticComplication = codes.some(c =>
                /^H36\.0|^H28\.0|^G63\.2|^N08\.3/.test(c || '')
            )
            if (hasDiabetes && hasDiabeticComplication) {
                // 应检查是否使用了联合编码 E1x.3, E1x.4 等
                const hasJointCode = codes.some(c => /^E1[0-4]\.[3-7]/.test(c || ''))
                if (!hasJointCode) return false
            }
            return true
        },
        getMessage: () => '存在需要联合诊断的情况，建议使用联合编码'
    },

    // --- 规则62: 出院西医其他诊断编码中存在医保停用码 ---
    {
        id: 'SC062',
        field: '出院其他诊断',
        ruleName: '诊断编码中存在医保停用码',
        description: '其他诊断编码不能使用医保停用码',
        auditLogic: '检查其他诊断编码是否为医保停用码',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            for (let i = 1; i < diagRows.length; i++) {
                if (diagRows[i].westCode && isDisabledCode(diagRows[i].westCode)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '其他诊断编码为医保停用码'
    },

    // --- 规则63: 出院西医其他诊断与患者性别不符 ---
    {
        id: 'SC063',
        field: '出院其他诊断',
        ruleName: '出院西医其他诊断与患者性别不符',
        description: '其他诊断应与患者性别相符',
        auditLogic: '审核其他诊断是否与患者性别相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const gender = form.basicInfo.gender
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            if (!gender) return true

            for (let i = 1; i < diagRows.length; i++) {
                const code = diagRows[i].westCode?.toUpperCase()
                if (!code) continue

                // 男性不能有妇产科诊断
                if (gender === 1 && /^O|^N[78]\d|^N9[0-8]/.test(code)) return false
                // 女性不能有男性特有诊断
                if (gender === 2 && /^N4\d|^N5[01]/.test(code)) return false
            }
            return true
        },
        getMessage: () => '其他诊断与患者性别不符'
    },

    // --- 规则64: 出院西医其他诊断与患者年龄不符 ---
    {
        id: 'SC064',
        field: '出院其他诊断',
        ruleName: '出院西医其他诊断与患者年龄不符',
        description: '其他诊断应与患者年龄相符',
        auditLogic: '审核其他诊断是否与患者年龄相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const age = form.basicInfo.age
            const ageInDays = form.basicInfo.ageInDays
            const diagRows = form.inpatientInfo?.diagnosisRows || []

            for (let i = 1; i < diagRows.length; i++) {
                const code = diagRows[i].westCode?.toUpperCase()
                if (!code) continue

                // P00-P96 新生儿疾病需要年龄<1岁
                if (/^P/.test(code)) {
                    if (age !== null && age >= 1) return false
                    if (ageInDays !== null && ageInDays >= 365) return false
                }
            }
            return true
        },
        getMessage: () => '其他诊断与患者年龄不符'
    },

    // --- 规则66: 出院西医其他诊断与新生儿出生体重不符 ---
    {
        id: 'SC066',
        field: '出院其他诊断',
        ruleName: '出院西医其他诊断与新生儿出生体重不符',
        description: '其他诊断中的体重相关诊断应与出生体重匹配',
        auditLogic: '当新生儿出生体重不为空时，审核其他诊断是否相符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const birthWeight = form.basicInfo.newbornBirthWeight
            const diagRows = form.inpatientInfo?.diagnosisRows || []
            if (!birthWeight) return true

            for (let i = 1; i < diagRows.length; i++) {
                const code = diagRows[i].westCode?.toUpperCase()
                if (!code) continue

                // 极低出生体重 P07.0 (体重<1000g)
                if (/^P07\.0/.test(code) && birthWeight >= 1000) return false
                // 低出生体重 P07.1 (体重1000-2499g)
                if (/^P07\.1/.test(code) && (birthWeight < 1000 || birthWeight >= 2500)) return false
            }
            return true
        },
        getMessage: () => '其他诊断与新生儿出生体重不符'
    },

    // --- 规则73: 手术操作编码中存在医保停用码 ---
    {
        id: 'SC073',
        field: '主手术',
        ruleName: '手术操作编码中存在医保停用码',
        description: '主手术编码不能使用医保停用码',
        auditLogic: '检查主手术编码是否为医保停用码',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const primaryOp = form.inpatientInfo?.surgeryRows?.[0]
            if (!primaryOp?.code) return true
            return !isDisabledCode(primaryOp.code)
        },
        getMessage: () => '主手术编码为医保停用码'
    },

    // --- 规则75: 主要手术及操作与患者年龄不符 ---
    {
        id: 'SC075',
        field: '主手术',
        ruleName: '主要手术及操作与患者年龄不符',
        description: '手术应与患者年龄相符',
        auditLogic: '审核主要手术是否与患者年龄相符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const age = form.basicInfo.age
            const primaryOp = form.inpatientInfo?.surgeryRows?.[0]
            if (!primaryOp?.code || age === null || age === undefined) return true

            const code = primaryOp.code
            // 儿童特有手术检查
            // TODO: 需要年龄-手术对照表
            return true
        },
        getMessage: () => '主手术与患者年龄不符'
    },

    // --- 规则77: 其他手术操作编码中存在医保停用码 ---
    {
        id: 'SC077',
        field: '其他手术',
        ruleName: '手术操作编码中存在医保停用码',
        description: '其他手术编码不能使用医保停用码',
        auditLogic: '检查其他手术编码是否为医保停用码',
        severity: 'error',
        category: 'format',
        isPreEvent: true,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            for (let i = 1; i < opRows.length; i++) {
                if (opRows[i].code && isDisabledCode(opRows[i].code)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '其他手术编码为医保停用码'
    },

    // --- 规则78: 其他手术及操作与患者性别不符 ---
    {
        id: 'SC078',
        field: '其他手术',
        ruleName: '其他手术及操作与患者性别不符',
        description: '其他手术应与患者性别相符',
        auditLogic: '审核其他手术是否与患者性别相符合',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const gender = form.basicInfo.gender
            const opRows = form.inpatientInfo?.surgeryRows || []
            if (!gender) return true

            for (let i = 1; i < opRows.length; i++) {
                const code = opRows[i].code
                if (!code) continue

                // 男性不能有妇产科手术 (68-75)
                if (gender === 1 && /^6[89]|^7[0-5]/.test(code)) return false
                // 女性不能有男性特有手术 (60-64)
                if (gender === 2 && /^6[0-4]/.test(code)) return false
            }
            return true
        },
        getMessage: () => '其他手术与患者性别不符'
    },

    // --- 规则79: 其他手术及操作与患者年龄不符 ---
    {
        id: 'SC079',
        field: '其他手术',
        ruleName: '其他手术及操作与患者年龄不符',
        description: '其他手术应与患者年龄相符',
        auditLogic: '审核其他手术是否与患者年龄相符',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要年龄-手术对照表
            return true
        },
        getMessage: () => '其他手术与患者年龄不符'
    },

    // --- 规则80: 手术部位不一致 ---
    {
        id: 'SC080',
        field: '手术操作',
        ruleName: '手术部位不一致',
        description: '同一天的手术应保持部位一致',
        auditLogic: '检查同一天手术的部位一致性',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要手术部位对照表
            return true
        },
        getMessage: () => '手术部位不一致'
    },

    // --- 规则82: 联合手术 ---
    {
        id: 'SC082',
        field: '手术操作',
        ruleName: '联合手术',
        description: '联合手术术式应使用联合手术编码',
        auditLogic: '检查是否应使用联合手术编码',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要联合手术对照表
            return true
        },
        getMessage: () => '应使用联合手术编码'
    },

    // --- 规则83: 手术与收费项目不符 ---
    {
        id: 'SC083',
        field: '手术操作',
        ruleName: '手术与收费项目不符',
        description: '手术应与收费项目对应',
        auditLogic: '检查手术和收费项目的对应关系',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (_form) => {
            // TODO: 需要手术-收费对照表
            return true
        },
        getMessage: () => '手术与收费项目不符'
    },

    // --- 规则86: 术者医师代码合理性 ---
    {
        id: 'SC086',
        field: '术者医师',
        ruleName: '术者医师代码合理性',
        description: '有手术时须有术者医师代码',
        auditLogic: '当有手术时，审核是否有术者医师代码',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            const hasOperation = opRows.some(op => isNotEmpty(op.code))
            if (hasOperation) {
                return opRows.some(op => op.code && isNotEmpty(op.surgeonCode))
            }
            return true
        },
        getMessage: () => '有手术时，术者医师代码不能为空'
    },

    // --- 规则88: 麻醉医师姓名合理性 ---
    {
        id: 'SC088',
        field: '麻醉医师',
        ruleName: '麻醉医师姓名合理性',
        description: '有麻醉方式时须有麻醉医师姓名',
        auditLogic: '当有麻醉方式时，审核是否有麻醉医师姓名',
        severity: 'error',
        category: 'required',
        isPreEvent: true,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            const hasAnesthesia = opRows.some(op => isNotEmpty(op.anesthesiaMethod))
            if (hasAnesthesia) {
                return opRows.some(op => op.anesthesiaMethod && isNotEmpty(op.anesthesiologistName))
            }
            return true
        },
        getMessage: () => '有麻醉方式时，麻醉医师姓名不能为空'
    },

    // --- 规则96: 颅脑损伤患者昏迷时间合理性 ---
    {
        id: 'SC096',
        field: '昏迷时间',
        ruleName: '颅脑损伤患者昏迷时间合理性',
        description: '昏迷时间>0时须有颅脑损伤诊断',
        auditLogic: '当昏迷时间不为0时，须有颅脑损伤相关编码',
        severity: 'error',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const comaAfter = form.inpatientInfo?.comaAfterAdmission
            const comaBefore = form.inpatientInfo?.comaBeforeAdmission

            const hasComaTime = (comaAfter?.days || 0) > 0 ||
                (comaAfter?.hours || 0) > 0 ||
                (comaBefore?.days || 0) > 0 ||
                (comaBefore?.hours || 0) > 0

            if (hasComaTime) {
                const diagRows = form.inpatientInfo?.diagnosisRows || []
                // 检查是否有颅脑损伤诊断 S00-S09
                const hasBrainInjury = diagRows.some(d =>
                    /^S0[0-9]/.test(d.westCode?.toUpperCase() || '')
                )
                return hasBrainInjury
            }
            return true
        },
        getMessage: () => '有昏迷时间但无颅脑损伤相关诊断'
    },

    // ========================================================================
    // 事后规则 - 提示 (绿色提示，规范性)
    // ========================================================================

    // --- 规则9: 现住址非空性 ---
    {
        id: 'SC009',
        field: '现住址',
        ruleName: '现住址非空性',
        description: '患者近期的常住地址',
        auditLogic: '审核现住址是否为空，若是则不通过',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const addr = form.basicInfo.currentAddress
            return isNotEmpty(addr?.province) || isNotEmpty(addr?.detail)
        },
        getMessage: () => '现住址建议填写'
    },

    // --- 规则15: 联系人与患者关系非空性 ---
    {
        id: 'SC015',
        field: '联系人关系',
        ruleName: '联系人与患者关系非空性',
        description: '联系人与患者之间的关系',
        auditLogic: '审核联系人与患者关系是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.basicInfo.contactRelation),
        getMessage: () => '联系人与患者关系建议填写'
    },

    // --- 规则17: 联系人地址非空性 ---
    {
        id: 'SC017',
        field: '联系人地址',
        ruleName: '联系人地址非空性',
        description: '联系人当前常住地址或工作单位地址',
        auditLogic: '审核联系人地址是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const addr = form.basicInfo.contactAddress
            return isNotEmpty(addr?.province) || isNotEmpty(addr?.detail)
        },
        getMessage: () => '联系人地址建议填写'
    },

    // --- 规则18: 联系人电话非空性 ---
    {
        id: 'SC018',
        field: '联系人电话',
        ruleName: '联系人电话非空性',
        description: '联系人的电话号码',
        auditLogic: '审核联系人电话是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.basicInfo.contactPhone),
        getMessage: () => '联系人电话建议填写'
    },

    // --- 规则27: 入院途径非空性 ---
    {
        id: 'SC027',
        field: '入院途径',
        ruleName: '入院途径非空性',
        description: '患者收治入院治疗的来源',
        auditLogic: '审核入院途径是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isValidNumber(form.inpatientInfo?.admissionRoute),
        getMessage: () => '入院途径建议填写'
    },

    // --- 规则29: 治疗类别非空性 ---
    {
        id: 'SC029',
        field: '治疗类别',
        ruleName: '治疗类别非空性',
        description: '对患者采用的主要医学治疗方法类别',
        auditLogic: '审核治疗类别是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isValidNumber(form.inpatientInfo?.treatmentCategory),
        getMessage: () => '治疗类别建议填写'
    },

    // --- 规则36: 出院科别非空性 ---
    {
        id: 'SC036',
        field: '出院科别',
        ruleName: '出院科别非空性',
        description: '患者出院时的科室名称',
        auditLogic: '审核出院科别是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.inpatientInfo?.dischargeDepartment),
        getMessage: () => '出院科别建议填写'
    },

    // --- 规则70: 入院病情非空性 ---
    {
        id: 'SC070',
        field: '入院病情',
        ruleName: '入院病情非空性',
        description: '对患者入院时病情评估情况',
        auditLogic: '审核入院病情是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const primaryDx = form.inpatientInfo?.diagnosisRows?.[0]
            return isNotEmpty(primaryDx?.admissionCondition)
        },
        getMessage: () => '入院病情建议填写'
    },

    // --- 规则112: 是否有31天内再住院计划非空性 ---
    {
        id: 'SC112',
        field: '再住院计划',
        ruleName: '是否有31天内再住院计划非空性',
        description: '患者出院后31天内是否有再住院安排',
        auditLogic: '审核是否有31天内再住院计划是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isValidNumber(form.inpatientInfo?.hasReadmissionPlan),
        getMessage: () => '是否有31天内再住院计划建议填写'
    },

    // --- 规则114: 主诊医师姓名非空性 ---
    {
        id: 'SC114',
        field: '主诊医师',
        ruleName: '主诊医师姓名非空性',
        description: '对于患者直接负责的最高级别医师',
        auditLogic: '审核主诊医师姓名是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.inpatientInfo?.attendingPhysicianName),
        getMessage: () => '主诊医师姓名建议填写'
    },

    // --- 规则123: 结算期间非空性 ---
    {
        id: 'SC123',
        field: '结算期间',
        ruleName: '结算期间非空性',
        description: '定点医疗机构与患者当次结算费用的起止时间',
        auditLogic: '审核结算期间是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const period = form.feeInfo?.settlementPeriod
            return isNotEmpty(period?.start) && isNotEmpty(period?.end)
        },
        getMessage: () => '结算期间建议填写'
    },

    // --- 规则125: 医保支付方式非空性 ---
    {
        id: 'SC125',
        field: '医保支付方式',
        ruleName: '医保支付方式非空性',
        description: '医保经办机构与定点医疗机构的付费方式',
        auditLogic: '审核医保支付方式是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const methods = form.feeInfo?.paymentMethod
            return methods && methods.length > 0
        },
        getMessage: () => '医保支付方式建议填写'
    },

    // --- 规则127: 定点医疗机构填报部门非空性 ---
    {
        id: 'SC127',
        field: '填报部门',
        ruleName: '定点医疗机构填报部门非空性',
        description: '定点医疗机构填报部门',
        auditLogic: '审核填报部门是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.reportingDepartment),
        getMessage: () => '填报部门建议填写'
    },

    // --- 规则128: 定点医疗机构填报人非空性 ---
    {
        id: 'SC128',
        field: '填报人',
        ruleName: '定点医疗机构填报人非空性',
        description: '定点医疗机构填报人',
        auditLogic: '审核填报人是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.reportingPerson),
        getMessage: () => '填报人建议填写'
    },

    // --- 规则3: 门(急)诊诊断与患儿年龄不符 ---
    {
        id: 'SC003',
        field: '年龄(天)',
        ruleName: '门(急)诊诊断与患儿年龄不符',
        description: '门(急)诊诊断编码P10~P15需天龄<365天',
        auditLogic: '门(急)诊诊断编码出现P10~P15，且天龄必须小于365天',
        severity: 'warning',
        category: 'consistency',
        isPreEvent: false,
        validate: (form) => {
            const ageInDays = form.basicInfo.ageInDays
            const diagRows = form.outpatientInfo?.diagnosisRows || []

            for (const row of diagRows) {
                if (row.diagnosisCode && /^P1[0-5]/.test(row.diagnosisCode.toUpperCase())) {
                    if (ageInDays !== null && ageInDays !== undefined && ageInDays >= 365) {
                        return false
                    }
                }
            }
            return true
        },
        getMessage: () => '门(急)诊诊断P10-P15需患儿天龄<365天'
    },

    // --- 规则6: 国籍规范性 ---
    {
        id: 'SC006',
        field: '国籍',
        ruleName: '国籍规范性',
        description: '国籍应按照GB/T 2659-2000标准填写',
        auditLogic: '审核国籍是否为标准代码或中文简称',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const nationality = form.basicInfo.nationality
            if (!nationality) return true
            // 常见国籍
            const validNationalities = ['中国', 'CHN', '156', '美国', 'USA', '840', '日本', 'JPN', '392']
            return validNationalities.includes(nationality.toUpperCase()) || nationality.length >= 2
        },
        getMessage: () => '国籍格式建议按GB/T 2659-2000标准填写'
    },

    // --- 规则8: 职业规范性 ---
    {
        id: 'SC008',
        field: '职业',
        ruleName: '职业规范性',
        description: '职业应按照GB/T2261.4-2003标准填写',
        auditLogic: '审核职业是否为标准代码',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const occupation = form.basicInfo.occupation
            if (!occupation) return true
            // 简化实现：检查是否为数字代码或常见职业
            return /^\d+$/.test(occupation) || occupation.length >= 2
        },
        getMessage: () => '职业格式建议按GB/T2261.4-2003标准填写'
    },

    // --- 规则10: 工作单位及地址合理性 ---
    {
        id: 'SC010',
        field: '工作单位',
        ruleName: '工作单位及地址合理性',
        description: '在职人员应填写工作单位名称和详细地址',
        auditLogic: '审核在职人员是否填写工作单位信息',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            // 如果有工作单位名称，建议填写地址
            if (isNotEmpty(form.basicInfo.workUnit)) {
                return isNotEmpty(form.basicInfo.workAddress)
            }
            return true
        },
        getMessage: () => '有工作单位时建议填写工作地址'
    },

    // --- 规则11: 单位电话合理性 ---
    {
        id: 'SC011',
        field: '单位电话',
        ruleName: '单位电话合理性',
        description: '在职人员工作单位电话号码',
        auditLogic: '审核在职人员是否填写单位电话',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            if (isNotEmpty(form.basicInfo.workUnit)) {
                return isNotEmpty(form.basicInfo.workPhone)
            }
            return true
        },
        getMessage: () => '有工作单位时建议填写单位电话'
    },

    // --- 规则12: 工作单位邮编合理性 ---
    {
        id: 'SC012',
        field: '工作单位邮编',
        ruleName: '工作单位邮编合理性',
        description: '工作单位详细地址的邮政编码',
        auditLogic: '审核工作单位邮编格式是否正确',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const postcode = form.basicInfo.workPostcode
            if (!postcode) return true
            return /^\d{6}$/.test(postcode)
        },
        getMessage: () => '工作单位邮编格式不正确（应为6位数字）'
    },

    // --- 规则19: 新生儿入院类型规范性 ---
    {
        id: 'SC019',
        field: '新生儿入院类型',
        ruleName: '新生儿入院类型规范性',
        description: '新生儿入院类型应为1-2代码',
        auditLogic: '审核新生儿入院类型是否为1或2',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const type = form.basicInfo.newbornAdmissionType
            if (!type) return true
            return ['1', '2'].includes(type)
        },
        getMessage: () => '新生儿入院类型应为1(正常新生儿)或2(患病新生儿)'
    },

    // --- 规则26: 新生儿入院体重合理性 ---
    {
        id: 'SC026',
        field: '新生儿入院体重',
        ruleName: '新生儿入院体重合理性',
        description: '新生儿入院体重应在500-6000g之间',
        auditLogic: '审核新生儿入院体重是否在合理范围',
        severity: 'warning',
        category: 'logic',
        isPreEvent: false,
        validate: (form) => {
            const weight = form.basicInfo.newbornAdmissionWeight
            if (weight === null || weight === undefined) return true
            return weight >= 500 && weight <= 6000
        },
        getMessage: () => '新生儿入院体重应在500-6000g之间'
    },

    // --- 规则28: 入院途径规范性 ---
    {
        id: 'SC028',
        field: '入院途径',
        ruleName: '入院途径规范性',
        description: '入院途径应为1-5或9代码',
        auditLogic: '审核入院途径是否为标准代码',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const route = form.inpatientInfo?.admissionRoute
            if (route === null || route === undefined) return true
            return [1, 2, 3, 4, 5, 9].includes(route)
        },
        getMessage: () => '入院途径代码不正确（应为1-5或9）'
    },

    // --- 规则30: 治疗类别规范性 ---
    {
        id: 'SC030',
        field: '治疗类别',
        ruleName: '治疗类别规范性',
        description: '治疗类别应为1-4代码',
        auditLogic: '审核治疗类别是否为标准代码',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const category = form.inpatientInfo?.treatmentCategory
            if (category === null || category === undefined) return true
            return [1, 2, 3, 4].includes(category)
        },
        getMessage: () => '治疗类别代码不正确（应为1-4）'
    },

    // --- 规则33: 转科科别规范性 ---
    {
        id: 'SC033',
        field: '转科科别',
        ruleName: '转科科别规范性',
        description: '有转科时应填写转科科别',
        auditLogic: '审核有转科时转科科别是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            // 如果入院科别和出院科别不同，应有转科记录
            const admDept = form.inpatientInfo?.admissionDepartment
            const disDept = form.inpatientInfo?.dischargeDepartment
            if (admDept && disDept && admDept !== disDept) {
                return isNotEmpty(form.inpatientInfo?.transferDepartment)
            }
            return true
        },
        getMessage: () => '入院和出院科别不同时建议填写转科科别'
    },

    // --- 规则84: 麻醉方式合理性 ---
    {
        id: 'SC084',
        field: '麻醉方式',
        ruleName: '麻醉方式合理性',
        description: '有手术时建议填写麻醉方式',
        auditLogic: '当有手术操作时，审核是否有麻醉方式',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            const hasOperation = opRows.some(op => isNotEmpty(op.code))
            if (hasOperation) {
                return opRows.some(op => op.code && isNotEmpty(op.anesthesiaMethod))
            }
            return true
        },
        getMessage: () => '有手术时建议填写麻醉方式'
    },

    // --- 规则87: 手术及操作起止时间 ---
    {
        id: 'SC087',
        field: '手术时间',
        ruleName: '手术及操作起止时间',
        description: '有手术时建议填写手术起止时间',
        auditLogic: '当有手术操作时，审核是否有手术起止时间',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            for (const op of opRows) {
                if (isNotEmpty(op.code)) {
                    if (!isNotEmpty(op.startTime) || !isNotEmpty(op.endTime)) {
                        return false
                    }
                }
            }
            return true
        },
        getMessage: () => '有手术时建议填写手术起止时间'
    },

    // --- 规则89: 麻醉起止时间 ---
    {
        id: 'SC089',
        field: '麻醉时间',
        ruleName: '麻醉起止时间',
        description: '有麻醉时建议填写麻醉起止时间',
        auditLogic: '当有麻醉时，审核是否有麻醉起止时间',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const opRows = form.inpatientInfo?.surgeryRows || []
            for (const op of opRows) {
                if (isNotEmpty(op.anesthesiaMethod)) {
                    if (!isNotEmpty(op.anesthesiaStartTime) || !isNotEmpty(op.anesthesiaEndTime)) {
                        return false
                    }
                }
            }
            return true
        },
        getMessage: () => '有麻醉时建议填写麻醉起止时间'
    },

    // --- 规则90: 呼吸机使用时间 ---
    {
        id: 'SC090',
        field: '呼吸机使用时间',
        ruleName: '呼吸机使用时间',
        description: '使用呼吸机时建议填写使用时长',
        auditLogic: '审核呼吸机使用时间是否填写合理',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const ventilator = form.inpatientInfo?.ventilatorDuration
            // 如果有呼吸机相关诊断或手术，建议填写
            // 简化实现：仅提示
            return true
        },
        getMessage: () => '使用呼吸机时建议填写使用时长'
    },

    // --- 规则97: 重症监护病房类型 ---
    {
        id: 'SC097',
        field: 'ICU类型',
        ruleName: '重症监护病房类型',
        description: '进入ICU时建议填写ICU类型',
        auditLogic: '当有ICU记录时，审核是否填写ICU类型',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const icuRecords = form.inpatientInfo?.icuRecords || []
            for (const record of icuRecords) {
                if (!isNotEmpty(record.icuType)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '进入ICU时建议填写ICU类型'
    },

    // --- 规则98: 重症监护病房进入时间 ---
    {
        id: 'SC098',
        field: 'ICU进入时间',
        ruleName: '重症监护病房进入时间',
        description: '进入ICU时建议填写进入时间',
        auditLogic: '当有ICU记录时，审核是否填写进入时间',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const icuRecords = form.inpatientInfo?.icuRecords || []
            for (const record of icuRecords) {
                if (!isNotEmpty(record.entryTime)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '进入ICU时建议填写进入时间'
    },

    // --- 规则101: 输血品种 ---
    {
        id: 'SC101',
        field: '输血品种',
        ruleName: '输血品种',
        description: '有输血时建议填写输血品种',
        auditLogic: '当有输血记录时，审核是否填写输血品种',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const transfusions = form.inpatientInfo?.transfusionRecords || []
            for (const record of transfusions) {
                if (!isNotEmpty(record.bloodType)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '有输血时建议填写输血品种'
    },

    // --- 规则102: 输血量 ---
    {
        id: 'SC102',
        field: '输血量',
        ruleName: '输血量',
        description: '有输血时建议填写输血量',
        auditLogic: '当有输血记录时，审核是否填写输血量',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => {
            const transfusions = form.inpatientInfo?.transfusionRecords || []
            for (const record of transfusions) {
                if (!isValidNumber(record.volume)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '有输血时建议填写输血量'
    },

    // --- 规则115: 责任护士姓名非空性 ---
    {
        id: 'SC115',
        field: '责任护士',
        ruleName: '责任护士姓名非空性',
        description: '对患者护理直接负责的最高级别护士',
        auditLogic: '审核责任护士姓名是否为空',
        severity: 'warning',
        category: 'required',
        isPreEvent: false,
        validate: (form) => isNotEmpty(form.inpatientInfo?.primaryNurseName),
        getMessage: () => '责任护士姓名建议填写'
    },

    // --- 规则124: 结算期间合理性 ---
    {
        id: 'SC124',
        field: '结算期间',
        ruleName: '结算期间合理性',
        description: '结算期间应在入出院时间范围内',
        auditLogic: '审核结算期间是否与入出院时间匹配',
        severity: 'warning',
        category: 'consistency',
        isPreEvent: false,
        validate: (form, context) => {
            const period = form.feeInfo?.settlementPeriod
            if (!period?.start || !period?.end) return true
            if (!context?.admissionTime || !context?.dischargeTime) return true

            const settleStart = new Date(period.start)
            const settleEnd = new Date(period.end)

            // 结算期间应在入出院时间附近
            return settleStart >= context.admissionTime && settleEnd <= context.dischargeTime
        },
        getMessage: () => '结算期间应在入出院时间范围内'
    },

    // --- 规则126: 医保支付方式规范性 ---
    {
        id: 'SC126',
        field: '医保支付方式',
        ruleName: '医保支付方式规范性',
        description: '医保支付方式应为标准代码',
        auditLogic: '审核医保支付方式是否为标准代码',
        severity: 'warning',
        category: 'format',
        isPreEvent: false,
        validate: (form) => {
            const methods = form.feeInfo?.paymentMethod || []
            const validMethods = [1, 2, 3, 4, 5, 6, 9]
            return methods.every(m => validMethods.includes(m))
        },
        getMessage: () => '医保支付方式代码不正确'
    }
]

// ==================== 校验引擎 ====================

/**
 * 执行所有质控规则校验
 */
export function validateSettlementForm(
    form: SettlementForm,
    context?: QCContext,
    ruleFilter?: (rule: QCRule) => boolean
): SettlementQCReport {
    const rulesToRun = ruleFilter ? QC_RULES.filter(ruleFilter) : QC_RULES
    const results: QCValidationResult[] = []

    for (const rule of rulesToRun) {
        try {
            const passed = rule.validate(form, context)

            if (!passed) {
                results.push({
                    ruleId: rule.id,
                    field: rule.field,
                    message: rule.getMessage(form),
                    severity: rule.severity,
                    passed: false
                })
            }
        } catch (e) {
            console.warn(`Rule ${rule.id} validation error:`, e)
        }
    }

    // 按严重程度排序：error > warning > info
    const severityOrder = { error: 0, warning: 1, info: 2 }
    results.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])

    const errorCount = results.filter(r => r.severity === 'error').length
    const warningCount = results.filter(r => r.severity === 'warning').length

    return {
        isValid: errorCount === 0,
        errorCount,
        warningCount,
        results
    }
}

/**
 * 只校验事前规则 (上传前必须通过)
 */
export function validatePreEventRules(form: SettlementForm, context?: QCContext): SettlementQCReport {
    return validateSettlementForm(form, context, rule => rule.isPreEvent)
}

/**
 * 只校验事后规则 (数据筛查)
 */
export function validatePostEventRules(form: SettlementForm, context?: QCContext): SettlementQCReport {
    return validateSettlementForm(form, context, rule => !rule.isPreEvent)
}

/**
 * 只校验必填项
 */
export function validateRequiredFields(form: SettlementForm): SettlementQCReport {
    return validateSettlementForm(form, undefined, rule => rule.category === 'required')
}

/**
 * 只校验格式
 */
export function validateFormats(form: SettlementForm): SettlementQCReport {
    return validateSettlementForm(form, undefined, rule => rule.category === 'format')
}

/**
 * 根据分类获取规则
 */
export function getRulesByCategory(category: QCRule['category']): QCRule[] {
    return QC_RULES.filter(rule => rule.category === category)
}

/**
 * 获取规则统计
 */
export function getRuleStats(): {
    total: number
    byCategory: Record<string, number>
    bySeverity: Record<string, number>
    preEventCount: number
    postEventCount: number
} {
    const byCategory: Record<string, number> = {}
    const bySeverity: Record<string, number> = {}
    let preEventCount = 0
    let postEventCount = 0

    for (const rule of QC_RULES) {
        byCategory[rule.category] = (byCategory[rule.category] || 0) + 1
        bySeverity[rule.severity] = (bySeverity[rule.severity] || 0) + 1
        if (rule.isPreEvent) preEventCount++
        else postEventCount++
    }

    return {
        total: QC_RULES.length,
        byCategory,
        bySeverity,
        preEventCount,
        postEventCount
    }
}

/**
 * 导出规则JSON (用于前端展示规则说明)
 */
export function exportRulesAsJSON(): object[] {
    return QC_RULES.map(rule => ({
        id: rule.id,
        field: rule.field,
        ruleName: rule.ruleName,
        description: rule.description,
        auditLogic: rule.auditLogic,
        severity: rule.severity,
        category: rule.category,
        isPreEvent: rule.isPreEvent
    }))
}
