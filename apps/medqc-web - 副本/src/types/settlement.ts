/**
 * 医保结算清单数据类型定义
 * Medical Insurance Settlement Form Types
 */

// ==================== 基本信息 ====================
export interface SettlementBasicInfo {
    // 机构信息
    institutionName: string          // 定点医疗机构名称
    institutionCode: string          // 定点医疗机构代码
    serialNumber: string             // 清单流水号
    insuranceNumber: string          // 医保编号
    caseNumber: string               // 病案号
    settlementLevel: string          // 医保结算等级
    reportDate: string               // 申报时间

    // 患者基本信息
    patientName: string              // 姓名
    gender: 1 | 2 | null             // 性别 1.男 2.女
    birthDate: string                // 出生日期
    age: number | null               // 年龄
    ageInDays: number | null         // 不足1岁年龄(天)
    nationality: string              // 国籍
    ethnicity: string                // 民族
    idCardType: string               // 患者证件类别
    idCardNumber: string             // 患者证件号码
    occupation: string               // 职业

    // 地址信息
    currentAddress: {
        province: string
        city: string
        county: string
        detail: string
    }

    // 工作单位
    workUnit: string                 // 工作单位名称
    workAddress: string              // 工作单位地址
    workPhone: string                // 单位电话
    workPostcode: string             // 邮编

    // 联系人信息
    contactName: string              // 联系人姓名
    contactRelation: string          // 关系
    contactAddress: {
        province: string
        city: string
        county: string
        detail: string
    }
    contactPhone: string             // 电话

    // 医保信息
    insuranceType: string            // 医保类型
    specialPersonType: string        // 特殊人员类型
    insuredArea: string              // 参保地

    // 新生儿信息
    newbornAdmissionType: string     // 新生儿入院类型
    newbornBirthWeight: number | null    // 新生儿出生体重(克)
    newbornAdmissionWeight: number | null // 新生儿入院体重(克)
}

// ==================== 门诊慢特病诊疗信息 ====================
export interface OutpatientDiagnosisRow {
    id: number
    diagnosisName: string            // 诊断名称
    diagnosisCode: string            // 诊断代码
    procedureName: string            // 手术及操作名称
    procedureCode: string            // 手术及操作代码
}

export interface SettlementOutpatientInfo {
    department: string               // 诊断科室
    visitDate: string                // 就诊日期
    diagnosisRows: OutpatientDiagnosisRow[]
}

// ==================== 住院诊疗信息 ====================
export interface InpatientDiagnosisRow {
    id: number
    westDiagnosis: string            // 出院西医诊断
    westCode: string                 // 西医疾病代码
    admissionCondition: string       // 入院病情
    tcmDiagnosis: string             // 出院中医诊断
    tcmCode: string                  // 中医疾病代码
    tcmAdmissionCondition: string    // 中医入院病情
}

export interface SurgeryRow {
    id: number
    name: string                     // 手术及操作名称
    code: string                     // 手术及操作代码
    date: string                     // 手术及操作日期
    startTime: string                // 手术开始时间
    endTime: string                  // 手术结束时间
    anesthesiaMethod: string         // 麻醉方式
    anesthesiaStartTime: string      // 麻醉开始时间
    anesthesiaEndTime: string        // 麻醉结束时间
    surgeonName: string              // 术者医师姓名
    surgeonCode: string              // 术者医师代码
    anesthesiologistName: string     // 麻醉医师姓名
    anesthesiologistCode: string     // 麻醉医师代码
}

export interface ICURow {
    id: number
    icuType: string                  // 重症监护病房类型
    entryTime: string                // 进重症监护室时间
    exitTime: string                 // 出重症监护室时间
    totalHours: number | null        // 合计（小时）
}

// 输血记录
export interface TransfusionRecord {
    id: number
    bloodType: string                // 输血品种
    volume: number | null            // 输血量
    unit: string                     // 输血计量单位
}

export interface SettlementInpatientInfo {
    // 住院类型
    hospitalizationType: 1 | 2 | null  // 1.住院 2.日间手术

    // 入院途径
    admissionRoute: 1 | 2 | 3 | 9 | null  // 1.急诊 2.门诊 3.其他机构转入 9.其他

    // 治疗类别
    treatmentCategory: 1 | 2 | 3 | null   // 1.西医 2.中医 3.中西医

    // 入院信息
    admissionTime: string            // 入院时间
    admissionDepartment: string      // 入院科别
    transferDepartment: string       // 转科科别

    // 出院信息
    dischargeTime: string            // 出院时间
    dischargeDepartment: string      // 出院科别
    actualLOS: number | null         // 实际住院天数

    // 门急诊诊断
    emergencyWestDiagnosis: string   // 门（急）诊诊断（西医）
    emergencyWestCode: string        // 西医疾病代码
    emergencyTCMDiagnosis: string    // 门（急）诊诊断（中医）
    emergencyTCMCode: string         // 中医疾病代码

    // 诊断表格
    diagnosisRows: InpatientDiagnosisRow[]
    diagnosisCount: number           // 诊断代码计数

    // 手术表格
    surgeryRows: SurgeryRow[]
    surgeryCount: number             // 手术及操作代码计数

    // 呼吸机使用
    ventilatorDays: number | null
    ventilatorHours: number | null
    ventilatorMinutes: number | null
    ventilatorDuration: number | null  // 呼吸机使用时长(小时)

    // 昏迷时间
    comaBeforeAdmission: { days: number | null; hours: number | null; minutes: number | null }
    comaAfterAdmission: { days: number | null; hours: number | null; minutes: number | null }

    // ICU记录
    icuRows: ICURow[]
    icuRecords: ICURow[]             // 别名，兼容QC规则

    // 输血记录
    transfusionRecords: TransfusionRecord[]

    // 输血信息 (legacy)
    bloodType: string                // 输血品种
    bloodVolume: string              // 输血量
    bloodUnit: string                // 输血计量单位

    // 护理天数
    specialNursingDays: number | null   // 特级护理天数
    level1NursingDays: number | null    // 一级护理天数
    level2NursingDays: number | null    // 二级护理天数
    level3NursingDays: number | null    // 三级护理天数

    // 离院方式
    dischargeMethod: 1 | 2 | 3 | 4 | 5 | 9 | null
    transferInstitutionName: string  // 拟接收机构名称
    transferInstitutionCode: string  // 拟接收机构代码

    // 再住院计划
    hasReadmissionPlan: 1 | 2 | null  // 1.无 2.有
    readmissionPurpose: string        // 目的

    // 责任护士
    primaryNurseName: string          // 责任护士姓名
    primaryNurseCode: string          // 责任护士代码

    // 主诊医师
    attendingPhysicianName: string   // 主诊医师姓名
    attendingPhysicianCode: string   // 主诊医师代码
}

// ==================== 医疗收费信息 ====================
export interface FeeItemRow {
    itemName: string                 // 项目名称
    amount: number | null            // 金额
    classA: number | null            // 甲类
    classB: number | null            // 乙类
    selfPay: number | null           // 自费
    other: number | null             // 其他
}

export interface SettlementFeeInfo {
    businessSerialNumber: string     // 业务流水号
    invoiceCode: string              // 票据代码
    invoiceNumber: string            // 票据号码
    settlementPeriod: {
        start: string
        end: string
    }

    // 费用明细
    feeItems: FeeItemRow[]
    totalAmount: FeeItemRow          // 金额合计

    // 基金支付
    fundPayments: {
        itemName: string
        amount: number | null
    }[]

    // 个人支付
    personalSelfPay: number | null   // 个人自付
    personalSelfExpense: number | null // 个人自费
    personalAccountPay: number | null  // 个人账户支付
    personalCashPay: number | null     // 个人现金支付

    // 医保支付方式
    paymentMethod: number[]          // 1-6 多选
}

// ==================== 完整结算清单 ====================
export interface SettlementForm {
    basicInfo: SettlementBasicInfo
    outpatientInfo: SettlementOutpatientInfo
    inpatientInfo: SettlementInpatientInfo
    feeInfo: SettlementFeeInfo

    // 填报信息
    reportingDepartment: string      // 医疗机构填报部门
    reportingPerson: string          // 医疗机构填报人
    insuranceAgency: string          // 医保机构
    insuranceAgent: string           // 医保机构经办人
}

// ==================== QC 验证结果 ====================
export interface QCValidationResult {
    ruleId: string
    field: string
    message: string
    severity: 'error' | 'warning' | 'info'
    passed: boolean
}

export interface SettlementQCReport {
    isValid: boolean
    errorCount: number
    warningCount: number
    results: QCValidationResult[]
}

// ==================== 费用项目常量 ====================
export const FEE_ITEM_NAMES = [
    '（一）综合医疗服务类',
    '1.一般医疗服务费',
    '2.一般治疗操作费',
    '3.护理费',
    '4.其他费用',
    '（二）诊断类',
    '5.病理诊断费',
    '6.实验室诊断费',
    '7.影像学诊断费',
    '8.临床诊断项目费',
    '（三）治疗类',
    '9.非手术治疗项目费',
    '10.临床物理治疗费',
    '11.手术治疗费',
    '12.麻醉费',
    '13.手术费',
    '（四）康复类',
    '14.康复费',
    '（五）中医类',
    '15.中医诊断',
    '16.中医治疗',
    '（六）西药类',
    '17.西药费',
    '（七）中药类',
    '18.中成药费',
    '19.中草药费',
    '（八）血液和血液制品类',
    '20.血费',
    '（九）耗材类',
    '21.检查用一次性医用材料费',
    '22.治疗用一次性医用材料费',
    '23.手术用一次性医用材料费',
    '（十）其他类',
    '24.其他费'
] as const

export const FUND_PAY_ITEMS = [
    '基本医疗保险统筹基金支付',
    '基本医疗保险个人账户支出',
    '大病保险资金支付',
    '医疗救助资金支付',
    '公务员医疗补助资金支付',
    '大额医疗费用补助资金支付',
    '企业补充医疗保险基金支付',
    '其他支付'
] as const
