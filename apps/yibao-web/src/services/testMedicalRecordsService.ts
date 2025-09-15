/**
 * 测试病历数据服务
 * 负责加载和转换Yibao项目中的测试病历数据
 */

// 定义Yibao测试病历数据类型
export interface YibaoTestRecord {
  record_id: string
  created_at: string
  patient: {
    patient_id: string
    name: string
    age: number
    gender: string
    id_card: string
    phone: string
    insurance_type: string
    insurance_number: string
  }
  visit: {
    visit_id: string
    visit_type: string
    visit_date: string
    department: string
    doctor: string
    hospital_level: string
    admission_days: number | null
  }
  diagnoses: Array<{
    diagnosis_id: string
    diagnosis_code: string
    diagnosis_name: string
    diagnosis_type: string
    diagnosis_date: string
  }>
  drug_orders: Array<{
    order_id: string
    drug_code: string
    drug_name: string
    dosage: string
    frequency: string
    duration: string
    route: string
    category: string
    unit_price: number
    quantity: number
    total_amount: number
  }>
  summary: {
    total_drug_cost: number
    drug_count: number
    diagnosis_count: number
  }
  test_scenario: {
    name: string
    rule_type: string
    expected_result: string
    description: string
  }
}

// 定义医生端demo所需的数据格式
export interface DemoFormData {
  patient: {
    age: number
    gender: 'M' | 'F' | 'U'
    insurance_type: string
  }
  visit: {
    type: 'OUTPATIENT' | 'INPATIENT'
    id: string
    department: string
  }
  diagnosis: {
    main: {
      code: string
    }
    secondary: string[]
  }
  orders: Array<{
    drug: {
      code: string
    }
    dose: number | null
    frequency: string
    route: string
  }>
}

// 定义选择器选项类型
export interface SampleOption {
  label: string
  value: string
  record: YibaoTestRecord
}

class TestMedicalRecordsService {
  private records: YibaoTestRecord[] = []
  private isLoaded = false

  constructor() {
    this.loadRecords()
  }

  /**
   * 加载测试病历数据
   */
  private async loadRecords() {
    if (this.isLoaded) return

    try {
      // 使用fetch来加载JSON数据，避免Vite导入路径问题
      const response = await fetch('/test_medical_records.json')
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      this.records = await response.json() as YibaoTestRecord[]
      this.isLoaded = true
      console.log(`✅ 成功加载 ${this.records.length} 条测试病历数据`)
    } catch (error) {
      console.error('❌ 加载测试病历数据失败:', error)
      // 使用备用的内置测试数据
      this.records = this.generateFallbackTestData()
      this.isLoaded = true
    }
  }

  /**
   * 确保数据已加载
   */
  private async ensureLoaded() {
    if (!this.isLoaded) {
      await this.loadRecords()
    }
  }

  /**
   * 获取所有测试病历记录
   */
  async getAllRecords(): Promise<YibaoTestRecord[]> {
    await this.ensureLoaded()
    return this.records
  }

  /**
   * 根据ID获取特定病历记录
   */
  async getRecordById(recordId: string): Promise<YibaoTestRecord | null> {
    await this.ensureLoaded()
    return this.records.find(record => record.record_id === recordId) || null
  }

  /**
   * 获取用于下拉选择器的选项列表
   */
  async getSampleOptions(): Promise<SampleOption[]> {
    await this.ensureLoaded()
    return this.records
      .filter(record => record && record.patient && record.visit && record.test_scenario)
      .map((record, index) => ({
        label: `${record.patient?.name || '未知患者'} - ${record.visit?.department || '未知科室'} - ${record.test_scenario?.name || '未知场景'}`,
        value: record.record_id,
        record
      }))
  }

  /**
   * 将Yibao格式的病历数据转换为医生端demo所需格式
   */
  convertToFormData(record: YibaoTestRecord): DemoFormData {
    // 转换性别格式
    const convertGender = (gender: string): 'M' | 'F' | 'U' => {
      switch (gender) {
        case '男': return 'M'
        case '女': return 'F'
        default: return 'U'
      }
    }

    // 转换就诊类型
    const convertVisitType = (visitType: string): 'OUTPATIENT' | 'INPATIENT' => {
      switch (visitType) {
        case '住院': return 'INPATIENT'
        case '门诊':
        case '急诊':
        default: return 'OUTPATIENT'
      }
    }

    // 转换医保类型
    const convertInsuranceType = (insuranceType: string): string => {
      const insuranceMap: Record<string, string> = {
        '城镇职工': 'employee',
        '城镇居民': 'resident', 
        '新农合': 'rural',
        '自费': 'self_pay'
      }
      return insuranceMap[insuranceType] || 'basic'
    }

    // 转换给药途径
    const convertRoute = (route: string): string => {
      const routeMap: Record<string, string> = {
        '口服': 'po',
        '静脉注射': 'iv',
        '肌肉注射': 'im',
        '外用': 'topical',
        '吸入': 'inhalation'
      }
      return routeMap[route] || 'po'
    }

    // 转换用药频次
    const convertFrequency = (frequency: string): string => {
      const frequencyMap: Record<string, string> = {
        '每日1次': 'qd',
        '每日2次': 'bid', 
        '每日3次': 'tid',
        '每日4次': 'qid',
        '每8小时1次': 'q8h',
        '每12小时1次': 'q12h'
      }
      return frequencyMap[frequency] || frequency
    }

    return {
      patient: {
        age: record.patient.age,
        gender: convertGender(record.patient.gender),
        insurance_type: convertInsuranceType(record.patient.insurance_type)
      },
      visit: {
        type: convertVisitType(record.visit.visit_type),
        id: record.visit.visit_id,
        department: record.visit.department
      },
      diagnosis: {
        main: {
          code: record.diagnoses[0]?.diagnosis_code || ''
        },
        secondary: record.diagnoses.slice(1).map(d => d.diagnosis_code)
      },
      orders: record.drug_orders.map(order => ({
        drug: {
          code: order.drug_code
        },
        dose: parseFloat(order.dosage.replace(/[^\d.]/g, '')) || null,
        frequency: convertFrequency(order.frequency),
        route: convertRoute(order.route)
      }))
    }
  }

  /**
   * 获取测试场景统计信息
   */
  async getScenarioStats() {
    await this.ensureLoaded()
    const stats: Record<string, number> = {}
    this.records.forEach(record => {
      const scenario = record.test_scenario.name
      stats[scenario] = (stats[scenario] || 0) + 1
    })
    return stats
  }

  /**
   * 根据测试场景筛选病历
   */
  async getRecordsByScenario(scenarioType: string): Promise<YibaoTestRecord[]> {
    await this.ensureLoaded()
    return this.records.filter(record =>
      record.test_scenario.rule_type === scenarioType
    )
  }

  /**
   * 根据科室筛选病历
   */
  async getRecordsByDepartment(department: string): Promise<YibaoTestRecord[]> {
    await this.ensureLoaded()
    return this.records.filter(record =>
      record.visit.department === department
    )
  }

  /**
   * 生成备用测试数据
   */
  private generateFallbackTestData(): YibaoTestRecord[] {
    return [
      {
        id: 'fallback-001',
        patient_name: '张三',
        patient_id: 'P001',
        gender: '男',
        age: 45,
        admission_date: '2024-01-15',
        discharge_date: '2024-01-20',
        diagnosis: '高血压',
        medications: [
          {
            name: '硝苯地平缓释片',
            code: 'M001',
            dosage: '30mg',
            frequency: '每日一次',
            duration: '7天'
          }
        ],
        procedures: [],
        total_cost: 1200.50,
        insurance_type: '职工医保',
        department: '心内科',
        doctor: '李医生',
        expected_violations: []
      },
      {
        id: 'fallback-002',
        patient_name: '李四',
        patient_id: 'P002',
        gender: '女',
        age: 32,
        admission_date: '2024-01-16',
        discharge_date: '2024-01-18',
        diagnosis: '感冒',
        medications: [
          {
            name: '阿莫西林胶囊',
            code: 'M002',
            dosage: '500mg',
            frequency: '每日三次',
            duration: '5天'
          }
        ],
        procedures: [],
        total_cost: 350.00,
        insurance_type: '居民医保',
        department: '内科',
        doctor: '王医生',
        expected_violations: []
      }
    ]
  }
}

// 创建单例实例
export const testMedicalRecordsService = new TestMedicalRecordsService()

export default testMedicalRecordsService
