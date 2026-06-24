export type PaymentGroupType = 'all' | 'base' | 'high' | 'low'
export type PaymentStatusFilter = 'all' | 'profit' | 'loss'

export interface PaymentMonitoringRow {
  id: number
  caseNo: string
  deptKey: string
  deptName: string
  drg: string
  actualCost: number
  payment: number
  baselinePayment: number
  weight?: number
  dipScore?: number
  ruleHint: string
  controlTip: string
}

export interface PaymentMonitoringTrendPoint {
  day: number
  actualCost: number
  payment: number
  paymentRate: number
}

export interface PaymentMonitoringOverview {
  caseCount: number
  actualCost: number
  payment: number
  profit: number
  paymentRate: number
  lossCases: number
  baseCases: number
  highCases: number
  lowCases: number
}

export interface PaymentMonitoringRule {
  groupType: Exclude<PaymentGroupType, 'all'>
  title: string
  trigger: string
  suggestion: string
  color: 'processing' | 'warning' | 'error'
}

export interface PaymentMonitoringOption {
  label: string
  value: string
}

const round1 = (value: number) => Math.round(value * 10) / 10

export const paymentMonitoringDeptOptions: PaymentMonitoringOption[] = [
  { label: '全部科室', value: 'all' },
  { label: '呼吸内科专业', value: 'respiratory' },
  { label: '心血管内科专业', value: 'cardiology' },
  { label: '普通外科专业', value: 'general-surgery' },
  { label: '骨科专业', value: 'orthopedics' },
  { label: '儿科', value: 'pediatrics' },
  { label: '神经内科专业', value: 'neurology' },
]

export const paymentMonitoringGroupOptions: PaymentMonitoringOption[] = [
  { label: '全部组别', value: 'all' },
  { label: '基础组', value: 'base' },
  { label: '费用极高组', value: 'high' },
  { label: '费用极低组', value: 'low' },
]

export const paymentMonitoringRules: PaymentMonitoringRule[] = [
  {
    groupType: 'base',
    title: '基础组',
    trigger: '成本消耗率 80% - 120%',
    suggestion: '按标准路径执行，重点监控重复检查、日均费用和住院日波动。',
    color: 'processing',
  },
  {
    groupType: 'high',
    title: '费用极高组',
    trigger: '成本消耗率 > 120%',
    suggestion: '优先复核耗材、治疗项目与影像检查，定位超费主因并出具整改建议。',
    color: 'error',
  },
  {
    groupType: 'low',
    title: '费用极低组',
    trigger: '成本消耗率 < 80%',
    suggestion: '排查治疗不足、漏计费与出院前结算异常，防止“低耗但低质”风险。',
    color: 'warning',
  },
]

// 参考“2025年1-12月病案与DIP关联数据”重建
// 总体特征：平均支付率约 58%，科室结构以呼吸/心内/普外/骨科/儿科为主
export const paymentMonitoringRows: PaymentMonitoringRow[] = [
  {
    id: 1,
    caseNo: '#202512-0001',
    deptKey: 'respiratory',
    deptName: '呼吸内科专业',
    drg: 'J44.0',
    actualCost: 6350,
    payment: 4020,
    baselinePayment: 5200,
    ruleHint: '慢阻肺急性加重',
    controlTip: '重点核查抗感染联合用药与重复检验频次',
  },
  {
    id: 2,
    caseNo: '#202512-0002',
    deptKey: 'respiratory',
    deptName: '呼吸内科专业',
    drg: 'J15.9',
    actualCost: 4100,
    payment: 2530,
    baselinePayment: 3600,
    ruleHint: '肺炎常见路径',
    controlTip: '控制日均耗材与床旁检查次数',
  },
  {
    id: 3,
    caseNo: '#202512-0003',
    deptKey: 'respiratory',
    deptName: '呼吸内科专业',
    drg: 'J18.0',
    actualCost: 2180,
    payment: 1230,
    baselinePayment: 2600,
    ruleHint: '低龄肺炎住院',
    controlTip: '注意低费用组是否存在漏计费或治疗不足',
  },
  {
    id: 4,
    caseNo: '#202512-0004',
    deptKey: 'cardiology',
    deptName: '心血管内科专业',
    drg: 'I25.1',
    actualCost: 8120,
    payment: 4510,
    baselinePayment: 6800,
    ruleHint: '冠心病介入前后',
    controlTip: '复核高值耗材与术后监测项目',
  },
  {
    id: 5,
    caseNo: '#202512-0005',
    deptKey: 'cardiology',
    deptName: '心血管内科专业',
    drg: 'I25.1:88.5500',
    actualCost: 7320,
    payment: 4290,
    baselinePayment: 6200,
    ruleHint: '冠脉造影路径',
    controlTip: '同日重复造影项目需专审',
  },
  {
    id: 6,
    caseNo: '#202512-0006',
    deptKey: 'cardiology',
    deptName: '心血管内科专业',
    drg: 'G45.0',
    actualCost: 3350,
    payment: 1940,
    baselinePayment: 3150,
    ruleHint: '短暂性脑缺血发作',
    controlTip: '监测检验组合是否超路径建议',
  },
  {
    id: 7,
    caseNo: '#202512-0007',
    deptKey: 'general-surgery',
    deptName: '普通外科专业',
    drg: 'Z51.5',
    actualCost: 5280,
    payment: 3210,
    baselinePayment: 4380,
    ruleHint: '肿瘤支持治疗',
    controlTip: '重点关注治疗项目与检查占比',
  },
  {
    id: 8,
    caseNo: '#202512-0008',
    deptKey: 'general-surgery',
    deptName: '普通外科专业',
    drg: 'M51:11',
    actualCost: 3920,
    payment: 2470,
    baselinePayment: 3700,
    ruleHint: '腰椎间盘疾病',
    controlTip: '控制非必要影像复查与治疗项目',
  },
  {
    id: 9,
    caseNo: '#202512-0009',
    deptKey: 'general-surgery',
    deptName: '普通外科专业',
    drg: 'Z51.1:99.2503',
    actualCost: 4850,
    payment: 3020,
    baselinePayment: 4100,
    ruleHint: '化疗相关住院',
    controlTip: '核对药占比与支持治疗费用边界',
  },
  {
    id: 10,
    caseNo: '#202512-0010',
    deptKey: 'orthopedics',
    deptName: '骨科专业',
    drg: 'M51:11',
    actualCost: 9630,
    payment: 5220,
    baselinePayment: 7350,
    ruleHint: '骨科手术后康复',
    controlTip: '核查高值耗材与康复治疗组合',
  },
  {
    id: 11,
    caseNo: '#202512-0011',
    deptKey: 'orthopedics',
    deptName: '骨科专业',
    drg: 'S72.0',
    actualCost: 11250,
    payment: 6050,
    baselinePayment: 8400,
    ruleHint: '股骨近端骨折',
    controlTip: '术中耗材与术后检查项目超标需复盘',
  },
  {
    id: 12,
    caseNo: '#202512-0012',
    deptKey: 'orthopedics',
    deptName: '骨科专业',
    drg: 'T84.0',
    actualCost: 6710,
    payment: 3890,
    baselinePayment: 5600,
    ruleHint: '内固定相关并发症',
    controlTip: '重点核查抗感染与耗材追加项目',
  },
  {
    id: 13,
    caseNo: '#202512-0013',
    deptKey: 'pediatrics',
    deptName: '儿科',
    drg: 'J20.9',
    actualCost: 1720,
    payment: 860,
    baselinePayment: 2100,
    ruleHint: '急性支气管炎',
    controlTip: '低费用组重点排查诊疗完整性与费用归集',
  },
  {
    id: 14,
    caseNo: '#202512-0014',
    deptKey: 'pediatrics',
    deptName: '儿科',
    drg: 'J18.0',
    actualCost: 2140,
    payment: 1090,
    baselinePayment: 2550,
    ruleHint: '儿科肺炎',
    controlTip: '监测抗菌药与雾化治疗组合',
  },
  {
    id: 15,
    caseNo: '#202512-0015',
    deptKey: 'pediatrics',
    deptName: '儿科',
    drg: 'A09.9',
    actualCost: 1380,
    payment: 720,
    baselinePayment: 1850,
    ruleHint: '感染性腹泻',
    controlTip: '低成本病例需回看文书和计费一致性',
  },
  {
    id: 16,
    caseNo: '#202512-0016',
    deptKey: 'neurology',
    deptName: '神经内科专业',
    drg: 'G45.0',
    actualCost: 3510,
    payment: 2100,
    baselinePayment: 3250,
    ruleHint: '脑血管短暂缺血',
    controlTip: '控制影像复查频次，避免路径外检查堆叠',
  },
  {
    id: 17,
    caseNo: '#202512-0017',
    deptKey: 'neurology',
    deptName: '神经内科专业',
    drg: 'I63.9',
    actualCost: 6240,
    payment: 3690,
    baselinePayment: 5200,
    ruleHint: '脑梗死住院管理',
    controlTip: '重点盯住检验、治疗与住院日匹配度',
  },
  {
    id: 18,
    caseNo: '#202512-0018',
    deptKey: 'neurology',
    deptName: '神经内科专业',
    drg: 'G40.9',
    actualCost: 2860,
    payment: 1710,
    baselinePayment: 2680,
    ruleHint: '癫痫相关住院',
    controlTip: '核查药物调整与监测项目必要性',
  },
]

// 近30日（万元）趋势：围绕真实月度均值折算，支付率稳定在57%-60%
const trendActualWan = [
  510, 516, 522, 528, 534, 541, 548, 554, 562, 569, 576, 582, 589, 595, 602, 610, 618, 625, 633,
  640, 648, 655, 663, 670, 678, 686, 694, 688, 676, 662,
]

const trendPaymentWan = [
  296, 300, 304, 307, 311, 315, 319, 323, 327, 331, 334, 338, 342, 346, 350, 354, 358, 362, 366,
  369, 373, 377, 381, 385, 389, 393, 397, 392, 387, 380,
]

export const paymentMonitoringTrend: PaymentMonitoringTrendPoint[] = trendActualWan.map(
  (actualCost, index) => {
    const payment = trendPaymentWan[index]
    return {
      day: index + 1,
      actualCost,
      payment,
      paymentRate: round1((payment / actualCost) * 100),
    }
  },
)

export function calcCostRate(
  row: Pick<PaymentMonitoringRow, 'actualCost' | 'baselinePayment'>,
): number {
  return round1((row.actualCost / row.baselinePayment) * 100)
}

export function calcPaymentRate(row: Pick<PaymentMonitoringRow, 'actualCost' | 'payment'>): number {
  return round1((row.payment / row.actualCost) * 100)
}

export function resolveGroupType(
  row: Pick<PaymentMonitoringRow, 'actualCost' | 'baselinePayment'>,
): Exclude<PaymentGroupType, 'all'> {
  const costRate = calcCostRate(row)
  if (costRate > 120) return 'high'
  if (costRate < 80) return 'low'
  return 'base'
}

export function getPaymentGroupLabel(groupType: Exclude<PaymentGroupType, 'all'>): string {
  return (
    paymentMonitoringGroupOptions.find((option) => option.value === groupType)?.label || groupType
  )
}

export function getPaymentGroupColor(
  groupType: Exclude<PaymentGroupType, 'all'>,
): 'processing' | 'warning' | 'error' {
  if (groupType === 'high') return 'error'
  if (groupType === 'low') return 'warning'
  return 'processing'
}

export function filterPaymentMonitoringRows(
  rows: PaymentMonitoringRow[],
  filters: {
    deptKey?: string
    groupType?: PaymentGroupType
    status?: PaymentStatusFilter
  } = {},
): PaymentMonitoringRow[] {
  const { deptKey = 'all', groupType = 'all', status = 'all' } = filters

  return rows.filter((row) => {
    if (deptKey !== 'all' && row.deptKey !== deptKey) return false

    const resolvedGroupType = resolveGroupType(row)
    if (groupType !== 'all' && resolvedGroupType !== groupType) return false

    const profit = row.payment - row.actualCost
    if (status === 'profit' && profit < 0) return false
    if (status === 'loss' && profit >= 0) return false

    return true
  })
}

export function getPaymentMonitoringOverview(
  rows: PaymentMonitoringRow[],
): PaymentMonitoringOverview {
  const summary = rows.reduce(
    (acc, row) => {
      acc.caseCount += 1
      acc.actualCost += row.actualCost
      acc.payment += row.payment
      if (row.payment - row.actualCost < 0) acc.lossCases += 1

      const groupType = resolveGroupType(row)
      if (groupType === 'high') acc.highCases += 1
      if (groupType === 'low') acc.lowCases += 1
      if (groupType === 'base') acc.baseCases += 1

      return acc
    },
    {
      caseCount: 0,
      actualCost: 0,
      payment: 0,
      lossCases: 0,
      baseCases: 0,
      highCases: 0,
      lowCases: 0,
    },
  )

  const profit = summary.payment - summary.actualCost
  return {
    ...summary,
    profit,
    paymentRate: summary.actualCost > 0 ? round1((summary.payment / summary.actualCost) * 100) : 0,
  }
}
