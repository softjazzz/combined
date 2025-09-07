/**
 * 医疗文书分类测试工具
 * 用于验证和测试新的层级化分类系统
 */

import { ExtractedDocument } from '../types/medical'
import { EnhancedDocumentClassifier } from '../services/llm/enhancedDocumentClassifier'
import { DocumentClassificationAdapter } from '../services/database/documentClassificationAdapter'

export interface TestCase {
  title: string
  content: string
  expectedCategory: string
  expectedType: string
  description?: string
}

export interface TestResult {
  testCase: TestCase
  actualCategory: string
  actualType: string
  confidence: number
  method: string
  passed: boolean
  details?: any
}

export interface TestSuite {
  name: string
  testCases: TestCase[]
}

export class ClassificationTester {
  private classifier: EnhancedDocumentClassifier
  private adapter: DocumentClassificationAdapter

  constructor() {
    this.classifier = new EnhancedDocumentClassifier()
    this.adapter = new DocumentClassificationAdapter()
  }

  /**
   * 运行测试套件
   */
  async runTestSuite(testSuite: TestSuite): Promise<TestResult[]> {
    const results: TestResult[] = []

    for (const testCase of testSuite.testCases) {
      const result = await this.runSingleTest(testCase)
      results.push(result)
    }

    return results
  }

  /**
   * 运行单个测试
   */
  private async runSingleTest(testCase: TestCase): Promise<TestResult> {
    // 创建测试文档
    const document: ExtractedDocument = {
      id: 'test_doc',
      title: testCase.title,
      content: testCase.content,
      confidence: 1.0,
      extractedAt: new Date(),
      type: 'DAILY_PROGRESS_NOTE' as any // 临时值
    }

    // 执行分类
    const classification = this.classifier.classify(document)

    // 检查结果
    const passed = classification.category === testCase.expectedCategory && 
                  classification.type === testCase.expectedType

    return {
      testCase,
      actualCategory: classification.category,
      actualType: classification.type,
      confidence: classification.confidence,
      method: classification.method,
      passed,
      details: classification.details
    }
  }

  /**
   * 生成测试报告
   */
  generateTestReport(results: TestResult[]): any {
    const totalTests = results.length
    const passedTests = results.filter(r => r.passed).length
    const failedTests = totalTests - passedTests

    const categoryStats = new Map<string, { total: number, passed: number }>()
    const typeStats = new Map<string, { total: number, passed: number }>()
    const methodStats = new Map<string, { total: number, passed: number }>()

    results.forEach(result => {
      // 统计分类准确率
      const expectedCategory = result.testCase.expectedCategory
      if (!categoryStats.has(expectedCategory)) {
        categoryStats.set(expectedCategory, { total: 0, passed: 0 })
      }
      const catStat = categoryStats.get(expectedCategory)!
      catStat.total++
      if (result.actualCategory === expectedCategory) {
        catStat.passed++
      }

      // 统计类型准确率
      const expectedType = result.testCase.expectedType
      if (!typeStats.has(expectedType)) {
        typeStats.set(expectedType, { total: 0, passed: 0 })
      }
      const typeStat = typeStats.get(expectedType)!
      typeStat.total++
      if (result.actualType === expectedType) {
        typeStat.passed++
      }

      // 统计方法准确率
      const method = result.method
      if (!methodStats.has(method)) {
        methodStats.set(method, { total: 0, passed: 0 })
      }
      const methodStat = methodStats.get(method)!
      methodStat.total++
      if (result.passed) {
        methodStat.passed++
      }
    })

    return {
      summary: {
        totalTests,
        passedTests,
        failedTests,
        accuracy: totalTests > 0 ? (passedTests / totalTests * 100).toFixed(2) + '%' : '0%'
      },
      categoryAccuracy: Object.fromEntries(
        Array.from(categoryStats.entries()).map(([cat, stat]) => [
          cat, 
          {
            ...stat,
            accuracy: stat.total > 0 ? (stat.passed / stat.total * 100).toFixed(2) + '%' : '0%'
          }
        ])
      ),
      typeAccuracy: Object.fromEntries(
        Array.from(typeStats.entries()).map(([type, stat]) => [
          type,
          {
            ...stat,
            accuracy: stat.total > 0 ? (stat.passed / stat.total * 100).toFixed(2) + '%' : '0%'
          }
        ])
      ),
      methodPerformance: Object.fromEntries(
        Array.from(methodStats.entries()).map(([method, stat]) => [
          method,
          {
            ...stat,
            accuracy: stat.total > 0 ? (stat.passed / stat.total * 100).toFixed(2) + '%' : '0%'
          }
        ])
      ),
      failedCases: results.filter(r => !r.passed).map(r => ({
        title: r.testCase.title,
        expected: `${r.testCase.expectedCategory}/${r.testCase.expectedType}`,
        actual: `${r.actualCategory}/${r.actualType}`,
        confidence: r.confidence,
        method: r.method
      }))
    }
  }

  /**
   * 创建标准测试套件
   */
  static createStandardTestSuite(): TestSuite {
    return {
      name: '医疗文书分类标准测试套件',
      testCases: [
        // 入院记录类测试
        {
          title: '入院记录',
          content: '患者张三，男，65岁，因"胸痛3天"入院。主诉：胸痛3天。现病史：患者3天前无明显诱因出现胸痛...',
          expectedCategory: 'admission_record',
          expectedType: 'admission_record',
          description: '标准入院记录'
        },
        {
          title: '入院诊断',
          content: '入院诊断：1.冠心病 2.高血压病',
          expectedCategory: 'admission_record',
          expectedType: 'admission_diagnosis',
          description: '入院诊断记录'
        },

        // 病程记录类测试
        {
          title: '首次病程记录',
          content: '患者入院后病情稳定，完善相关检查。病情分析：根据患者症状和体征，考虑冠心病可能。诊疗计划：...',
          expectedCategory: 'progress_note',
          expectedType: 'first_progress_note',
          description: '首次病程记录'
        },
        {
          title: '主治医师查房记录',
          content: '主治医师查房：患者病情稳定，治疗有效，继续原治疗方案...',
          expectedCategory: 'progress_note',
          expectedType: 'attending_progress',
          description: '主治医师查房'
        },
        {
          title: '日常病程记录',
          content: '患者今日病情稳定，无特殊不适，继续观察治疗...',
          expectedCategory: 'progress_note',
          expectedType: 'daily_progress_note',
          description: '日常病程记录'
        },

        // 手术记录类测试
        {
          title: '术前小结',
          content: '术前小结：患者诊断明确，手术指征充分，术前准备完善，可行手术治疗...',
          expectedCategory: 'operation_record',
          expectedType: 'preoperative_summary',
          description: '术前小结'
        },
        {
          title: '手术记录',
          content: '手术记录：术前诊断：冠心病。手术过程：在全麻下行冠状动脉搭桥术。术中所见：...',
          expectedCategory: 'operation_record',
          expectedType: 'operation_record',
          description: '手术记录'
        },
        {
          title: '麻醉记录',
          content: '麻醉记录：麻醉方式：全身麻醉。麻醉效果：良好。术中生命体征平稳...',
          expectedCategory: 'operation_record',
          expectedType: 'anesthesia_record',
          description: '麻醉记录'
        },

        // 护理文书类测试
        {
          title: '护理记录单',
          content: '护理记录：患者意识清楚，生命体征平稳。护理措施：密切观察病情变化，按时给药...',
          expectedCategory: 'nursing_document',
          expectedType: 'nursing_record',
          description: '护理记录单'
        },
        {
          title: '体温单',
          content: '体温：36.5℃，脉搏：78次/分，呼吸：18次/分，血压：120/80mmHg',
          expectedCategory: 'nursing_document',
          expectedType: 'temperature_chart',
          description: '体温单记录'
        },
        {
          title: '护理评估单',
          content: '护理评估：患者自理能力良好，无跌倒风险，营养状况良好。风险评估：低风险...',
          expectedCategory: 'nursing_document',
          expectedType: 'nursing_assessment',
          description: '护理评估单'
        },

        // 出院记录类测试
        {
          title: '出院记录',
          content: '出院记录：患者经治疗后病情好转，症状缓解，康复出院。出院诊断：冠心病。出院医嘱：...',
          expectedCategory: 'discharge_record',
          expectedType: 'discharge_record',
          description: '出院记录'
        },
        {
          title: '出院小结',
          content: '出院小结：患者住院期间治疗顺利，病情稳定，可以出院...',
          expectedCategory: 'discharge_record',
          expectedType: 'discharge_summary',
          description: '出院小结'
        },

        // 检查报告类测试
        {
          title: 'CT检查报告',
          content: 'CT检查报告：胸部CT平扫+增强：双肺纹理增粗，心影增大...',
          expectedCategory: 'examination_report',
          expectedType: 'imaging_examination',
          description: 'CT检查报告'
        },
        {
          title: '血常规报告',
          content: '血常规检查：白细胞计数：6.5×10^9/L，红细胞计数：4.2×10^12/L...',
          expectedCategory: 'examination_report',
          expectedType: 'laboratory_test',
          description: '血常规检查报告'
        },
        {
          title: '心电图报告',
          content: '心电图检查：窦性心律，心率78次/分，ST段轻度压低...',
          expectedCategory: 'examination_report',
          expectedType: 'special_examination',
          description: '心电图检查报告'
        },

        // 医嘱记录类测试
        {
          title: '长期医嘱',
          content: '长期医嘱：1.阿司匹林 100mg 口服 每日一次 2.美托洛尔 25mg 口服 每日两次...',
          expectedCategory: 'medical_order',
          expectedType: 'long_term_order',
          description: '长期医嘱记录'
        },
        {
          title: '临时医嘱',
          content: '临时医嘱：心电图检查 今日完成，血常规+生化全套 明日晨起空腹抽血...',
          expectedCategory: 'medical_order',
          expectedType: 'temporary_order',
          description: '临时医嘱记录'
        },
        {
          title: '医嘱执行记录',
          content: '医嘱执行记录：执行时间：2024-01-15 08:00，执行护士：李护士，执行情况：已完成给药...',
          expectedCategory: 'medical_order',
          expectedType: 'order_execution',
          description: '医嘱执行记录'
        }
      ]
    }
  }

  /**
   * 运行标准测试
   */
  async runStandardTest(): Promise<any> {
    const testSuite = ClassificationTester.createStandardTestSuite()
    const results = await this.runTestSuite(testSuite)
    const report = this.generateTestReport(results)
    
    console.log('=== 医疗文书分类测试报告 ===')
    console.log('总体统计:', report.summary)
    console.log('分类准确率:', report.categoryAccuracy)
    console.log('类型准确率:', report.typeAccuracy)
    console.log('方法性能:', report.methodPerformance)
    
    if (report.failedCases.length > 0) {
      console.log('失败案例:', report.failedCases)
    }
    
    return report
  }

  /**
   * 测试特定文书类型的识别能力
   */
  async testSpecificCategory(category: string, testCases: TestCase[]): Promise<TestResult[]> {
    const filteredCases = testCases.filter(tc => tc.expectedCategory === category)
    const results: TestResult[] = []

    for (const testCase of filteredCases) {
      const result = await this.runSingleTest(testCase)
      results.push(result)
    }

    return results
  }

  /**
   * 测试护理文书识别能力（重点测试）
   */
  async testNursingDocuments(): Promise<any> {
    const nursingTestCases: TestCase[] = [
      {
        title: '护理记录',
        content: '护理记录：患者神志清楚，精神可，饮食正常，大小便正常。护理措施：1.密切观察病情变化 2.按时给药 3.协助患者翻身',
        expectedCategory: 'nursing_document',
        expectedType: 'nursing_record'
      },
      {
        title: '生命体征记录',
        content: '生命体征：T:36.8℃ P:82次/分 R:20次/分 BP:130/85mmHg',
        expectedCategory: 'nursing_document',
        expectedType: 'temperature_chart'
      },
      {
        title: '护理计划',
        content: '护理计划：护理目标：预防并发症，促进康复。护理措施：1.病情观察 2.用药护理 3.心理护理',
        expectedCategory: 'nursing_document',
        expectedType: 'nursing_plan'
      }
    ]

    const results = await this.testSpecificCategory('nursing_document', nursingTestCases)
    const report = this.generateTestReport(results)
    
    console.log('=== 护理文书识别测试报告 ===')
    console.log(report)
    
    return report
  }

  /**
   * 测试医嘱记录识别能力（重点测试）
   */
  async testMedicalOrders(): Promise<any> {
    const orderTestCases: TestCase[] = [
      {
        title: '长期医嘱记录',
        content: '长期医嘱：1.低盐低脂饮食 2.阿司匹林肠溶片 100mg po qd 3.氯吡格雷片 75mg po qd',
        expectedCategory: 'medical_order',
        expectedType: 'long_term_order'
      },
      {
        title: '临时医嘱记录',
        content: '临时医嘱：1.心电图检查 st 2.胸片检查 st 3.血常规+生化全套 明日晨起空腹',
        expectedCategory: 'medical_order',
        expectedType: 'temporary_order'
      },
      {
        title: '医嘱执行单',
        content: '医嘱执行：08:00 阿司匹林100mg 已执行 执行护士：张护士 12:00 氯吡格雷75mg 已执行 执行护士：李护士',
        expectedCategory: 'medical_order',
        expectedType: 'order_execution'
      }
    ]

    const results = await this.testSpecificCategory('medical_order', orderTestCases)
    const report = this.generateTestReport(results)
    
    console.log('=== 医嘱记录识别测试报告 ===')
    console.log(report)
    
    return report
  }
}
