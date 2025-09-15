/**
 * 药品名称到编码的映射数据
 * 用于在用户界面中显示药品名称，后端处理时转换为编码
 */

export interface DrugInfo {
  code: string
  name: string
  category: string
  description?: string
}

// 药品映射数据
export const DRUG_MAPPING: DrugInfo[] = [
  // 测试用药品
  {
    code: 'DEMO_DRUG_INPATIENT',
    name: '住院专用药品',
    category: '测试药品',
    description: '仅限住院患者使用的示例药品'
  },
  {
    code: 'DEMO_DRUG_001',
    name: '儿童专用药品A',
    category: '测试药品',
    description: '限制儿童使用的示例药品'
  },
  {
    code: 'DEMO_DRUG_FEMALE',
    name: '女性专用药品',
    category: '测试药品',
    description: '仅限女性使用的示例药品'
  },
  
  // 常用药品
  {
    code: 'ASPIRIN_100MG',
    name: '阿司匹林肠溶片',
    category: '心血管用药',
    description: '100mg规格，用于心血管疾病预防'
  },
  {
    code: 'METFORMIN_500MG',
    name: '二甲双胍片',
    category: '内分泌用药',
    description: '500mg规格，用于2型糖尿病治疗'
  },
  {
    code: 'AMOXICILLIN_250MG',
    name: '阿莫西林胶囊',
    category: '抗感染药',
    description: '250mg规格，青霉素类抗生素'
  },
  {
    code: 'LISINOPRIL_10MG',
    name: '赖诺普利片',
    category: '心血管用药',
    description: '10mg规格，ACE抑制剂类降压药'
  },
  {
    code: 'OMEPRAZOLE_20MG',
    name: '奥美拉唑肠溶胶囊',
    category: '消化系统用药',
    description: '20mg规格，质子泵抑制剂'
  },
  {
    code: 'SIMVASTATIN_20MG',
    name: '辛伐他汀片',
    category: '心血管用药',
    description: '20mg规格，他汀类调脂药'
  },
  {
    code: 'CEPHALEXIN_500MG',
    name: '头孢氨苄胶囊',
    category: '抗感染药',
    description: '500mg规格，头孢菌素类抗生素'
  },
  {
    code: 'IBUPROFEN_400MG',
    name: '布洛芬缓释胶囊',
    category: '解热镇痛药',
    description: '400mg规格，非甾体抗炎药'
  },
  {
    code: 'ATORVASTATIN_20MG',
    name: '阿托伐他汀钙片',
    category: '心血管用药',
    description: '20mg规格，他汀类调脂药'
  },
  {
    code: 'LOSARTAN_50MG',
    name: '氯沙坦钾片',
    category: '心血管用药',
    description: '50mg规格，ARB类降压药'
  },
  
  // 儿童用药
  {
    code: 'CHILDREN_PARACETAMOL',
    name: '小儿对乙酰氨基酚混悬液',
    category: '儿童用药',
    description: '儿童专用退热药'
  },
  {
    code: 'CHILDREN_AMOXICILLIN',
    name: '小儿阿莫西林颗粒',
    category: '儿童用药',
    description: '儿童专用抗生素'
  },
  
  // 妇科用药
  {
    code: 'FOLIC_ACID_5MG',
    name: '叶酸片',
    category: '妇科用药',
    description: '5mg规格，用于孕期营养补充'
  },
  {
    code: 'IRON_SUPPLEMENT',
    name: '硫酸亚铁片',
    category: '妇科用药',
    description: '用于缺铁性贫血治疗'
  },
  
  // 老年用药
  {
    code: 'DONEPEZIL_5MG',
    name: '多奈哌齐片',
    category: '神经系统用药',
    description: '5mg规格，用于阿尔茨海默病治疗'
  },
  {
    code: 'CALCIUM_CARBONATE',
    name: '碳酸钙片',
    category: '骨科用药',
    description: '用于骨质疏松预防和治疗'
  }
]

// 创建名称到编码的映射
export const DRUG_NAME_TO_CODE_MAP = new Map<string, string>()
export const DRUG_CODE_TO_NAME_MAP = new Map<string, string>()

// 初始化映射
DRUG_MAPPING.forEach(drug => {
  DRUG_NAME_TO_CODE_MAP.set(drug.name, drug.code)
  DRUG_CODE_TO_NAME_MAP.set(drug.code, drug.name)
})

// 工具函数
export function getDrugCodeByName(name: string): string | undefined {
  return DRUG_NAME_TO_CODE_MAP.get(name)
}

export function getDrugNameByCode(code: string): string | undefined {
  return DRUG_CODE_TO_NAME_MAP.get(code)
}

export function searchDrugs(keyword: string): DrugInfo[] {
  if (!keyword) return DRUG_MAPPING
  
  const lowerKeyword = keyword.toLowerCase()
  return DRUG_MAPPING.filter(drug => 
    drug.name.toLowerCase().includes(lowerKeyword) ||
    drug.category.toLowerCase().includes(lowerKeyword) ||
    drug.description?.toLowerCase().includes(lowerKeyword)
  )
}

// 按分类分组的药品
export function getDrugsByCategory(): Record<string, DrugInfo[]> {
  const grouped: Record<string, DrugInfo[]> = {}
  
  DRUG_MAPPING.forEach(drug => {
    if (!grouped[drug.category]) {
      grouped[drug.category] = []
    }
    grouped[drug.category].push(drug)
  })
  
  return grouped
}
