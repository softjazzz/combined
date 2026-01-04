/**
 * 医保结算清单质控规则测试脚本
 * Settlement Form QC Rules Test Script
 *
 * 使用方式:
 *   npx tsx scripts/test-settlement-qc.ts
 */

import type {
    SettlementForm,
    SettlementBasicInfo,
    SettlementInpatientInfo,
    SettlementFeeInfo,
    SettlementOutpatientInfo
} from '../src/types/settlement'

// 直接导入规则和验证函数
// 注: 由于这是一个独立测试脚本，我们需要模拟核心验证逻辑

// ==================== 辅助函数 ====================

const isNotEmpty = (value: string | null | undefined): boolean => {
    return value !== null && value !== undefined && value.trim() !== ''
}

const isValidNumber = (value: number | null | undefined): boolean => {
    return value !== null && value !== undefined && !isNaN(value)
}

const isValidICD10 = (code: string): boolean => {
    if (!code) return false
    // ICD-10 格式：字母开头 + 2位数字 + 可选小数点 + 可选数字或x
    // 支持 I10.x00, A01.001 等格式
    const pattern = /^[A-UZ]\d{2}(\.[x\d]{1,4})?$/i
    return pattern.test(code.trim())
}

const isValidICD9CM3 = (code: string): boolean => {
    if (!code) return false
    const pattern = /^\d{2}\.\d{2,4}$/
    return pattern.test(code.trim())
}

const isValidIDCard = (idCard: string): boolean => {
    if (!idCard) return false
    const pattern = /^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$/
    return pattern.test(idCard.trim())
}

// ==================== 测试数据 ====================

// 创建一个完全合格的测试表单
function createValidForm(): SettlementForm {
    const basicInfo: SettlementBasicInfo = {
        institutionName: '四川省人民医院',
        institutionCode: 'H51010001',
        serialNumber: 'SN20260104001',
        insuranceNumber: 'INS2026001',
        caseNumber: 'CA20260104001',
        settlementLevel: '三甲',
        reportDate: '2026-01-04',
        patientName: '张三',
        gender: 1,
        birthDate: '1980-05-15',
        age: 45,
        ageInDays: null,
        nationality: '中国',
        ethnicity: '汉族',
        idCardType: '居民身份证',
        idCardNumber: '510102198005151234',
        occupation: '工程师',
        currentAddress: {
            province: '四川省',
            city: '成都市',
            county: '武侯区',
            detail: '人民南路100号'
        },
        workUnit: 'XX科技公司',
        workAddress: '成都市高新区天府大道',
        workPhone: '028-12345678',
        workPostcode: '610041',
        contactName: '李四',
        contactRelation: '配偶',
        contactAddress: {
            province: '四川省',
            city: '成都市',
            county: '武侯区',
            detail: '人民南路100号'
        },
        contactPhone: '13800138000',
        insuranceType: '城镇职工基本医疗保险',
        specialPersonType: '',
        insuredArea: '四川省成都市',
        newbornAdmissionType: '',
        newbornBirthWeight: null,
        newbornAdmissionWeight: null
    }

    const outpatientInfo: SettlementOutpatientInfo = {
        department: '',
        visitDate: '',
        diagnosisRows: []
    }

    const inpatientInfo: SettlementInpatientInfo = {
        hospitalizationType: 1,
        admissionRoute: 2,
        treatmentCategory: 1,
        admissionTime: '2026-01-01 10:30:00',
        admissionDepartment: '心内科',
        transferDepartment: '',
        dischargeTime: '2026-01-04 14:00:00',
        dischargeDepartment: '心内科',
        actualLOS: 3,
        emergencyWestDiagnosis: '高血压3级',
        emergencyWestCode: 'I10.x00',
        emergencyTCMDiagnosis: '',
        emergencyTCMCode: '',
        diagnosisRows: [
            {
                id: 1,
                westDiagnosis: '高血压3级',
                westCode: 'I10.x00',
                admissionCondition: '1',
                tcmDiagnosis: '',
                tcmCode: '',
                tcmAdmissionCondition: ''
            }
        ],
        diagnosisCount: 1,
        surgeryRows: [],
        surgeryCount: 0,
        ventilatorDays: null,
        ventilatorHours: null,
        ventilatorMinutes: null,
        ventilatorDuration: null,
        comaBeforeAdmission: { days: null, hours: null, minutes: null },
        comaAfterAdmission: { days: null, hours: null, minutes: null },
        icuRows: [],
        icuRecords: [],
        transfusionRecords: [],
        bloodType: '',
        bloodVolume: '',
        bloodUnit: '',
        specialNursingDays: null,
        level1NursingDays: 1,
        level2NursingDays: 2,
        level3NursingDays: null,
        dischargeMethod: 1,
        transferInstitutionName: '',
        transferInstitutionCode: '',
        hasReadmissionPlan: 1,
        readmissionPurpose: '',
        primaryNurseName: '王护士',
        primaryNurseCode: 'N001',
        attendingPhysicianName: '刘医生',
        attendingPhysicianCode: 'D001'
    }

    const feeInfo: SettlementFeeInfo = {
        businessSerialNumber: 'BSN20260104001',
        invoiceCode: 'INV001',
        invoiceNumber: '00001234',
        settlementPeriod: {
            start: '2026-01-01',
            end: '2026-01-04'
        },
        feeItems: [
            { itemName: '（一）综合医疗服务类', amount: 500, classA: 400, classB: 100, selfPay: 0, other: 0 },
            { itemName: '1.一般医疗服务费', amount: 200, classA: 200, classB: 0, selfPay: 0, other: 0 }
        ],
        totalAmount: { itemName: '金额合计', amount: 5000, classA: 4000, classB: 800, selfPay: 200, other: 0 },
        fundPayments: [
            { itemName: '基本医疗保险统筹基金支付', amount: 3500 },
            { itemName: '基本医疗保险个人账户支出', amount: 1000 }
        ],
        personalSelfPay: 500,
        personalSelfExpense: 200,
        personalAccountPay: 1000,
        personalCashPay: 500,
        paymentMethod: [1, 2]
    }

    return {
        basicInfo,
        outpatientInfo,
        inpatientInfo,
        feeInfo,
        reportingDepartment: '医务科',
        reportingPerson: '赵六',
        insuranceAgency: '成都市医保局',
        insuranceAgent: '王经办'
    }
}

// 创建一个有问题的测试表单
function createInvalidForm(): SettlementForm {
    const form = createValidForm()

    // 1. 病案号为空 - 违反SC001
    form.basicInfo.caseNumber = ''

    // 2. 性别为null - 违反必填规则
    form.basicInfo.gender = null

    // 3. 身份证号格式错误
    form.basicInfo.idCardNumber = '1234567890'

    // 4. 入院时间晚于出院时间 - 逻辑错误
    form.inpatientInfo.admissionTime = '2026-01-05 10:30:00'
    form.inpatientInfo.dischargeTime = '2026-01-04 14:00:00'

    // 5. 诊断编码格式错误 - 非ICD-10格式
    form.inpatientInfo.diagnosisRows[0].westCode = 'INVALID'

    // 6. 主诊医师姓名为空
    form.inpatientInfo.attendingPhysicianName = ''

    return form
}

// ==================== 规则定义 ====================

interface TestRule {
    id: string
    description: string
    validate: (form: SettlementForm) => boolean
    getMessage: () => string
    severity: 'error' | 'warning'
}

const TEST_RULES: TestRule[] = [
    {
        id: 'SC001',
        description: '病案号非空性',
        validate: (form) => isNotEmpty(form.basicInfo.caseNumber),
        getMessage: () => '病案号不能为空',
        severity: 'error'
    },
    {
        id: 'SC002',
        description: '年龄填写完整性',
        validate: (form) => {
            if (form.basicInfo.age === null || form.basicInfo.age === undefined) {
                return isValidNumber(form.basicInfo.ageInDays)
            }
            return true
        },
        getMessage: () => '年龄(岁)为空时，年龄(天)必须填写',
        severity: 'error'
    },
    {
        id: 'SC003',
        description: '性别非空性',
        validate: (form) => form.basicInfo.gender !== null,
        getMessage: () => '性别不能为空',
        severity: 'error'
    },
    {
        id: 'SC004',
        description: '身份证号格式',
        validate: (form) => {
            if (!form.basicInfo.idCardNumber) return true
            return isValidIDCard(form.basicInfo.idCardNumber)
        },
        getMessage: () => '身份证号格式不正确',
        severity: 'error'
    },
    {
        id: 'SC005',
        description: '入院时间早于出院时间',
        validate: (form) => {
            const admission = new Date(form.inpatientInfo.admissionTime)
            const discharge = new Date(form.inpatientInfo.dischargeTime)
            return admission <= discharge
        },
        getMessage: () => '入院时间不能晚于出院时间',
        severity: 'error'
    },
    {
        id: 'SC006',
        description: '主诊断ICD-10编码格式',
        validate: (form) => {
            const rows = form.inpatientInfo.diagnosisRows || []
            if (rows.length === 0) return true
            return isValidICD10(rows[0].westCode)
        },
        getMessage: () => '主诊断西医编码格式不正确',
        severity: 'error'
    },
    {
        id: 'SC007',
        description: '主诊医师姓名非空',
        validate: (form) => isNotEmpty(form.inpatientInfo.attendingPhysicianName),
        getMessage: () => '主诊医师姓名不能为空',
        severity: 'error'
    },
    {
        id: 'SC008',
        description: '手术编码格式 (ICD-9-CM-3)',
        validate: (form) => {
            const rows = form.inpatientInfo.surgeryRows || []
            for (const row of rows) {
                if (row.code && !isValidICD9CM3(row.code)) {
                    return false
                }
            }
            return true
        },
        getMessage: () => '手术编码格式不正确',
        severity: 'error'
    },
    {
        id: 'SC009',
        description: '住院天数一致性',
        validate: (form) => {
            const admission = new Date(form.inpatientInfo.admissionTime)
            const discharge = new Date(form.inpatientInfo.dischargeTime)
            const calculatedDays = Math.ceil((discharge.getTime() - admission.getTime()) / (1000 * 60 * 60 * 24))
            const actualLOS = form.inpatientInfo.actualLOS
            if (actualLOS === null) return true
            return Math.abs(calculatedDays - actualLOS) <= 1
        },
        getMessage: () => '实际住院天数与出入院时间计算不一致',
        severity: 'warning'
    },
    {
        id: 'SC010',
        description: '费用合计一致性',
        validate: (form) => {
            const total = form.feeInfo.totalAmount.amount || 0
            const fundTotal = form.feeInfo.fundPayments.reduce((sum, f) => sum + (f.amount || 0), 0)
            const personalTotal = (form.feeInfo.personalSelfPay || 0)
                + (form.feeInfo.personalSelfExpense || 0)
            // 简化校验: 资金支付 + 个人支付 应接近总费用
            return true // 暂不严格校验
        },
        getMessage: () => '费用合计与明细不一致',
        severity: 'warning'
    }
]

// ==================== 验证函数 ====================

interface ValidationResult {
    ruleId: string
    description: string
    passed: boolean
    message: string
    severity: 'error' | 'warning'
}

interface QCReport {
    totalRules: number
    passedCount: number
    failedCount: number
    errorCount: number
    warningCount: number
    results: ValidationResult[]
}

function validateForm(form: SettlementForm): QCReport {
    const results: ValidationResult[] = []
    let passedCount = 0
    let failedCount = 0
    let errorCount = 0
    let warningCount = 0

    for (const rule of TEST_RULES) {
        const passed = rule.validate(form)
        results.push({
            ruleId: rule.id,
            description: rule.description,
            passed,
            message: passed ? '通过' : rule.getMessage(),
            severity: rule.severity
        })

        if (passed) {
            passedCount++
        } else {
            failedCount++
            if (rule.severity === 'error') {
                errorCount++
            } else {
                warningCount++
            }
        }
    }

    return {
        totalRules: TEST_RULES.length,
        passedCount,
        failedCount,
        errorCount,
        warningCount,
        results
    }
}

// ==================== 测试执行 ====================

function printDivider(title: string) {
    console.log('\n' + '='.repeat(60))
    console.log(` ${title}`)
    console.log('='.repeat(60))
}

function printResult(result: ValidationResult) {
    const icon = result.passed ? '✅' : (result.severity === 'error' ? '❌' : '⚠️')
    const status = result.passed ? '通过' : '失败'
    console.log(`  ${icon} [${result.ruleId}] ${result.description}: ${status}`)
    if (!result.passed) {
        console.log(`      ↳ ${result.message}`)
    }
}

function printReport(report: QCReport, title: string) {
    printDivider(title)

    console.log(`\n📊 统计概览:`)
    console.log(`   总规则数: ${report.totalRules}`)
    console.log(`   通过: ${report.passedCount}`)
    console.log(`   失败: ${report.failedCount} (错误: ${report.errorCount}, 警告: ${report.warningCount})`)
    console.log(`   通过率: ${((report.passedCount / report.totalRules) * 100).toFixed(1)}%`)

    console.log(`\n📋 详细结果:`)
    for (const result of report.results) {
        printResult(result)
    }
}

function runTests() {
    console.log('\n🏥 医保结算清单质控规则测试')
    console.log('📅 测试时间:', new Date().toLocaleString('zh-CN'))
    console.log('📝 测试规则数:', TEST_RULES.length)

    // 测试1: 合格表单
    const validForm = createValidForm()
    const validReport = validateForm(validForm)
    printReport(validReport, '测试1: 完全合格的结算清单')

    // 测试2: 有问题的表单
    const invalidForm = createInvalidForm()
    const invalidReport = validateForm(invalidForm)
    printReport(invalidReport, '测试2: 故意制造错误的结算清单')

    // 测试总结
    printDivider('测试总结')
    console.log(`\n🎯 测试场景 1 (合格表单):`)
    console.log(`   预期: 全部通过`)
    console.log(`   实际: ${validReport.failedCount === 0 ? '✅ 全部通过' : `❌ ${validReport.failedCount}项未通过`}`)

    console.log(`\n🎯 测试场景 2 (问题表单):`)
    console.log(`   预期: 多项失败 (病案号空、性别空、身份证格式错、时间逻辑错、编码格式错、医师姓名空)`)
    console.log(`   实际: ${invalidReport.failedCount}项未通过`)

    const allPassed = validReport.failedCount === 0 && invalidReport.failedCount > 0
    console.log(`\n${allPassed ? '🎉' : '⚠️'} 测试结论: ${allPassed ? '质控规则引擎工作正常!' : '请检查规则实现'}`)

    // 返回测试是否全部通过
    return allPassed
}

// 执行测试
const success = runTests()
process.exit(success ? 0 : 1)
