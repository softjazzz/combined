/**
 * ICD 编码库 Mock 数据
 * 包含常用的 ICD-10 诊断编码和 ICD-9-CM-3 手术操作编码
 */

export interface ICDCode {
  code: string
  name: string
  category: string
  notes: string | null
  includes: string[]
  excludes: string[]
}

// Mock 数据：ICD-10 诊断编码（常用）
export const mockICD10Codes: ICDCode[] = [
  {
    code: 'I21.001',
    name: '急性前壁ST段抬高型心肌梗死',
    category: '循环系统疾病',
    notes: '限于有ST段抬高的急性前壁心肌梗死',
    includes: ['急性前壁心肌梗死伴ST段抬高'],
    excludes: ['陈旧性心肌梗死(I25.2)']
  },
  {
    code: 'I21.101',
    name: '急性下壁ST段抬高型心肌梗死',
    category: '循环系统疾病',
    notes: '限于有ST段抬高的急性下壁心肌梗死',
    includes: ['急性下壁心肌梗死伴ST段抬高'],
    excludes: ['陈旧性心肌梗死(I25.2)']
  },
  {
    code: 'I21.901',
    name: '急性心肌梗死，未特指',
    category: '循环系统疾病',
    notes: '部位不明确时使用',
    includes: ['急性心肌梗死NOS'],
    excludes: ['陈旧性心肌梗死(I25.2)']
  },
  {
    code: 'I10.x01',
    name: '高血压3级（极高危）',
    category: '循环系统疾病',
    notes: '收缩压≥180mmHg和/或舒张压≥110mmHg',
    includes: ['极高危组高血压'],
    excludes: ['继发性高血压(I15.-)']
  },
  {
    code: 'E11.901',
    name: '2型糖尿病',
    category: '内分泌、营养和代谢疾病',
    notes: '不伴有并发症的2型糖尿病',
    includes: ['成人发病型糖尿病', '非胰岛素依赖型糖尿病'],
    excludes: ['1型糖尿病(E10.-)']
  },
  {
    code: 'I50.001',
    name: '心力衰竭',
    category: '循环系统疾病',
    notes: '心功能不全，未特指左心或右心',
    includes: ['充血性心力衰竭', '心功能不全'],
    excludes: ['新生儿心力衰竭(P29.0)']
  },
  {
    code: 'J18.901',
    name: '肺炎，未特指病原体',
    category: '呼吸系统疾病',
    notes: '病原体不明的肺炎',
    includes: ['支气管肺炎NOS'],
    excludes: ['吸入性肺炎(J69.-)']
  },
  {
    code: 'J44.101',
    name: '慢性阻塞性肺疾病伴急性下呼吸道感染',
    category: '呼吸系统疾病',
    notes: 'COPD急性加重',
    includes: ['COPD伴急性加重'],
    excludes: ['肺气肿(J43.-)']
  },
  {
    code: 'J96.001',
    name: '急性呼吸衰竭',
    category: '呼吸系统疾病',
    notes: '急性起病的呼吸功能不全',
    includes: ['急性呼吸功能不全'],
    excludes: ['慢性呼吸衰竭(J96.1)']
  }
]

// Mock 数据：ICD-9-CM-3 手术操作编码（常用）
export const mockICD9Procedures: ICDCode[] = [
  {
    code: '36.0700',
    name: '经皮冠状动脉介入术',
    category: '心血管系统手术',
    notes: 'PCI，包括球囊扩张、支架置入',
    includes: ['冠状动脉支架置入术', '冠状动脉球囊扩张术'],
    excludes: ['冠状动脉旁路移植术(36.1-)']
  },
  {
    code: '36.1000',
    name: '冠状动脉旁路移植术',
    category: '心血管系统手术',
    notes: 'CABG手术',
    includes: ['搭桥手术'],
    excludes: ['经皮冠状动脉介入术(36.0-)']
  },
  {
    code: '37.6100',
    name: '主动脉内球囊反搏（IABP）',
    category: '心血管系统手术',
    notes: '机械性循环辅助装置',
    includes: ['IABP置入'],
    excludes: []
  },
  {
    code: '96.7100',
    name: '持续机械通气',
    category: '呼吸系统操作',
    notes: '呼吸机辅助通气',
    includes: ['机械通气', '呼吸机支持'],
    excludes: ['非侵入性通气(93.90)']
  },
  {
    code: '89.5400',
    name: '心电图检查',
    category: '诊断性操作',
    notes: '12导联心电图',
    includes: ['ECG'],
    excludes: ['动态心电图(89.52)']
  }
]

// 辅助函数：搜索 ICD-10 编码
export function searchICD10Codes(query: string): ICDCode[] {
  const q = query.toLowerCase()
  return mockICD10Codes.filter(
    code =>
      code.code.toLowerCase().includes(q) ||
      code.name.toLowerCase().includes(q) ||
      code.category.toLowerCase().includes(q)
  )
}

// 辅助函数：搜索 ICD-9-CM-3 编码
export function searchICD9Procedures(query: string): ICDCode[] {
  const q = query.toLowerCase()
  return mockICD9Procedures.filter(
    code =>
      code.code.toLowerCase().includes(q) ||
      code.name.toLowerCase().includes(q) ||
      code.category.toLowerCase().includes(q)
  )
}

// 辅助函数：根据编码获取详情
export function getICDCodeByCode(code: string, type: 'diagnosis' | 'procedure'): ICDCode | null {
  const codes = type === 'diagnosis' ? mockICD10Codes : mockICD9Procedures
  return codes.find(c => c.code === code) || null
}

// 辅助函数：模拟 LLM 编码推荐（基于疾病名称）
export function suggestICDCodes(diagnosisName: string): Array<ICDCode & { confidence: number }> {
  // 简单的关键词匹配（实际应该调用 LLM API）
  const keywords = diagnosisName.toLowerCase()

  let matches: Array<ICDCode & { confidence: number }> = []

  if (keywords.includes('心肌梗') || keywords.includes('心梗')) {
    matches = [
      { ...mockICD10Codes[0], confidence: 0.92 }, // I21.001
      { ...mockICD10Codes[2], confidence: 0.78 }, // I21.901
      { ...mockICD10Codes[1], confidence: 0.65 }  // I21.101
    ]
  } else if (keywords.includes('肺炎')) {
    matches = [
      { ...mockICD10Codes[6], confidence: 0.88 }, // J18.901
      { ...mockICD10Codes[7], confidence: 0.45 }  // J44.101
    ]
  } else if (keywords.includes('高血压')) {
    matches = [
      { ...mockICD10Codes[3], confidence: 0.85 }  // I10.x01
    ]
  } else if (keywords.includes('糖尿病')) {
    matches = [
      { ...mockICD10Codes[4], confidence: 0.90 }  // E11.901
    ]
  } else {
    // 默认返回最常见的3个
    matches = mockICD10Codes.slice(0, 3).map((code, idx) => ({
      ...code,
      confidence: 0.8 - idx * 0.1
    }))
  }

  return matches.slice(0, 3)
}
