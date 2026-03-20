// LLM QC Demo Service
// This service demonstrates the Phase 1 functionality of the LLM-integrated QC system

import type {
  EnhancedQCRule,
  CreateEnhancedRuleRequest,
  ComprehensiveQCResult
} from '@/types/enhanced-qc-rule'

import { llmIntegratedRulesService } from './llm-integrated-rules-service'
import { integratedQCEngine } from './integrated-qc-engine'
import { intelligentQCCache } from './intelligent-cache'

// Demo Data Generator
class DemoDataGenerator {
  static generateSamplePatientData(): Record<string, unknown> {
    return {
      patientId: 'demo-patient-001',
      patientName: '张三',
      admissionDate: '2024-12-24',
      documents: [
        {
          id: 'doc-admission-001',
          type: 'admission_record',
          content: `
入院记录

患者姓名：张三
性别：男
年龄：45岁
主诉：胸痛3小时
现病史：患者于3小时前无明显诱因出现胸痛，疼痛位于胸骨后，呈压榨性，向左肩背部放射，伴有出汗、恶心。
既往史：高血压病史5年，规律服用降压药物。
体格检查：
  生命体征：血压150/90mmHg，心率85次/分，呼吸18次/分，体温36.5℃
  心肺检查：心律齐，未闻及杂音，双肺呼吸音清晰
辅助检查：
  心电图：V1-V4导联ST段抬高
  心肌酶：肌钙蛋白I升高
初步诊断：
  1. 急性ST段抬高型心肌梗死
  2. 高血压病2级
          `,
          timestamp: '2024-12-24T08:30:00Z',
          author: '李医生',
          status: 'completed'
        },
        {
          id: 'doc-progress-001',
          type: 'progress_note',
          content: `
首次病程记录

患者张三，男，45岁，因"胸痛3小时"入院。
入院诊断：急性ST段抬高型心肌梗死，高血压病2级
病情分析：患者中年男性，急性起病，典型胸痛症状，心电图示ST段抬高，心肌酶升高，符合急性心肌梗死诊断。
诊疗计划：
1. 急诊PCI治疗
2. 双联抗血小板治疗
3. 他汀类药物调脂
4. ACEI类药物心脏保护
5. 严密监测生命体征
          `,
          timestamp: '2024-12-24T09:00:00Z',
          author: '李医生',
          status: 'completed'
        }
      ],
      orders: [
        {
          id: 'order-001',
          type: 'medication',
          content: '阿司匹林 100mg 口服 每日一次',
          timestamp: '2024-12-24T09:15:00Z',
          status: 'active',
          medicationName: '阿司匹林'
        },
        {
          id: 'order-002',
          type: 'procedure',
          content: '急诊冠状动脉介入治疗',
          timestamp: '2024-12-24T09:20:00Z',
          status: 'scheduled'
        }
      ],
      reports: [
        {
          id: 'report-001',
          type: 'laboratory',
          result: '肌钙蛋白I: 15.2 ng/mL (正常值 <0.04)',
          timestamp: '2024-12-24T08:45:00Z',
          abnormalFindings: ['肌钙蛋白I显著升高']
        }
      ],
      timeline: {
        events: [
          {
            timestamp: '2024-12-24T05:30:00Z',
            type: 'symptom_onset',
            description: '患者开始出现胸痛症状',
            significance: 'high'
          },
          {
            timestamp: '2024-12-24T08:30:00Z',
            type: 'admission',
            description: '患者入院',
            significance: 'high'
          }
        ],
        admissionTime: '2024-12-24T08:30:00Z'
      }
    }
  }

  static generateSampleRules(): CreateEnhancedRuleRequest[] {
    return [
      {
        rule_code: 'COMP_001',
        name: '入院记录完整性检查',
        description: '检查入院记录是否包含所有必需章节：主诉、现病史、既往史、体格检查、辅助检查、初步诊断',
        applicable_documents: ['admission_record'],
        rule_implementation: 'hybrid_analysis',
        alert_level: 'major',
        scoring_config: {
          default_deduction: 5,
          max_deduction: 20,
          weight_factor: 1.2
        },
        quality_logic: {
          check_type: 'content_analysis',
          logic_expression: 'check_required_sections',
          validation_criteria: [
            { field: 'chief_complaint', operator: 'exists', description: '必须包含主诉' },
            { field: 'present_illness', operator: 'exists', description: '必须包含现病史' },
            { field: 'past_history', operator: 'exists', description: '必须包含既往史' },
            { field: 'physical_examination', operator: 'exists', description: '必须包含体格检查' },
            { field: 'auxiliary_examination', operator: 'exists', description: '必须包含辅助检查' },
            { field: 'preliminary_diagnosis', operator: 'exists', description: '必须包含初步诊断' }
          ],
          llm_prompt_template: '请检查入院记录是否包含所有必需的医疗文书章节，重点关注内容的完整性和规范性。'
        },
        core_system_related: true,
        category: 'completeness',
        severity: 'major',
        max_score: 20,
        weight: 1.2,
        is_active: true
      },
      {
        rule_code: 'DUP_001',
        name: '文书重复内容检测',
        description: '检测入院记录与首次病程记录之间是否存在过度重复的内容',
        applicable_documents: ['admission_record', 'progress_note'],
        rule_implementation: 'semantic_llm',
        alert_level: 'minor',
        scoring_config: {
          default_deduction: 3,
          max_deduction: 10,
          weight_factor: 0.8
        },
        quality_logic: {
          check_type: 'content_analysis',
          logic_expression: 'detect_content_similarity',
          validation_criteria: [
            { field: 'similarity_threshold', operator: 'less_than', value: '80', description: '相似度不应超过80%' }
          ],
          llm_prompt_template: '请分析不同文书间的内容相似度，识别可能的复制粘贴行为。'
        },
        core_system_related: false,
        category: 'duplication',
        severity: 'minor',
        max_score: 10,
        weight: 0.8,
        is_active: true
      },
      {
        rule_code: 'ALERT_001',
        name: '书写时效性预警',
        description: '检查文书是否在规定时间内完成，生成相应的书写提醒',
        applicable_documents: ['admission_record', 'progress_note'],
        rule_implementation: 'logical_program',
        alert_level: 'major',
        scoring_config: {
          default_deduction: 8,
          max_deduction: 15,
          weight_factor: 1.0
        },
        quality_logic: {
          check_type: 'time_constraint',
          logic_expression: 'check_writing_timeliness',
          validation_criteria: [
            { field: 'admission_record_time', operator: 'less_than', value: '24', description: '入院记录应在24小时内完成' },
            { field: 'progress_note_time', operator: 'less_than', value: '8', description: '首次病程记录应在8小时内完成' }
          ]
        },
        core_system_related: true,
        category: 'writing_alerts',
        severity: 'major',
        max_score: 15,
        weight: 1.0,
        is_active: true
      }
    ]
  }
}

// Demo Service
export class LLMQCDemoService {
  private isInitialized = false

  async initializeDemo(): Promise<void> {
    if (this.isInitialized) {
      console.log('Demo already initialized')
      return
    }

    console.log('🚀 Initializing LLM QC Demo...')

    try {
      // 1. Create sample rules
      const sampleRules = DemoDataGenerator.generateSampleRules()
      const createdRules: EnhancedQCRule[] = []

      for (const ruleData of sampleRules) {
        try {
          const rule = await llmIntegratedRulesService.createEnhancedRule(ruleData)
          createdRules.push(rule)
          console.log(`✅ Created rule: ${rule.name}`)
        } catch (error: any) {
          console.log(`⚠️ Rule ${ruleData.name} may already exist: ${error.message}`)
        }
      }

      // 2. Warm up the cache
      await intelligentQCCache.warmCache(createdRules)

      // 3. Test rule configurations
      for (const rule of createdRules) {
        try {
          const testResult = await llmIntegratedRulesService.testRuleConfiguration(rule.id)
          console.log(`🧪 Rule test ${rule.rule_code}: ${testResult.isSuccessful ? 'PASSED' : 'FAILED'}`)
        } catch (error) {
          console.log(`⚠️ Rule test failed for ${rule.rule_code}`)
        }
      }

      this.isInitialized = true
      console.log('✅ Demo initialization completed!')

    } catch (error) {
      console.error('❌ Demo initialization failed:', error)
      throw error
    }
  }

  async runQCDemo(): Promise<ComprehensiveQCResult> {
    if (!this.isInitialized) {
      await this.initializeDemo()
    }

    console.log('🔍 Running QC Demo Analysis...')

    try {
      // 1. Generate sample patient data
      const patientData = DemoDataGenerator.generateSamplePatientData()
      console.log(`📋 Generated patient data for: ${patientData.patientName}`)

      // 2. Execute quality control analysis
      const startTime = Date.now()
      const qcResult = await integratedQCEngine.executeQualityControl(
        patientData,
        'cardiology', // Department ID
        { category: 'completeness' } // Filter for Phase 1 rules
      )
      const executionTime = Date.now() - startTime

      console.log(`⚡ QC Analysis completed in ${executionTime}ms`)
      console.log(`📊 Overall Score: ${qcResult.overallScore}/100`)
      console.log(`🚨 Risk Level: ${qcResult.riskLevel}`)
      console.log(`🔍 Rules Checked: ${qcResult.ruleResults.length}`)
      console.log(`⚠️ Issues Found: ${qcResult.ruleResults.reduce((sum, r) => sum + r.findings.length, 0)}`)

      // 3. Display detailed results
      this.displayDetailedResults(qcResult)

      return qcResult

    } catch (error: any) {
      console.error('❌ QC Demo failed:', error)
      throw error
    }
  }

  private displayDetailedResults(result: ComprehensiveQCResult): void {
    console.log('\n📋 Detailed QC Results:')
    console.log('=' .repeat(50))

    result.ruleResults.forEach((ruleResult: any,  index: any) => {
      console.log(`\n${index + 1}. ${ruleResult.ruleName} (${ruleResult.ruleCode})`)
      console.log(`   Status: ${ruleResult.isCompliant ? '✅ COMPLIANT' : '❌ NON-COMPLIANT'}`)
      console.log(`   Score: ${ruleResult.score}/100`)
      console.log(`   Confidence: ${ruleResult.confidence}%`)
      console.log(`   Execution Time: ${ruleResult.executionTime}ms`)

      if (ruleResult.findings.length > 0) {
        console.log('   Findings:')
        ruleResult.findings.forEach((finding: any,  fIndex: any) => {
          const severityIcon = finding.severity === 'critical' ? '🔴' : 
                              finding.severity === 'major' ? '🟡' : '🟢'
          console.log(`     ${fIndex + 1}. ${severityIcon} ${finding.description}`)
          if (finding.recommendation) {
            console.log(`        💡 ${finding.recommendation}`)
          }
        })
      }

      if (ruleResult.medicalReasoning) {
        console.log(`   Medical Reasoning: ${ruleResult.medicalReasoning}`)
      }
    })

    console.log('\n📈 Summary:')
    console.log(`   ${result.summary}`)

    if (result.crossRuleAnalysis) {
      console.log('\n🔗 Cross-Rule Analysis:')
      console.log(`   Correlated Issues: ${result.crossRuleAnalysis.correlatedIssues}`)
      console.log(`   Systemic Problems: ${result.crossRuleAnalysis.systemicProblems}`)
      console.log(`   Priority Recommendations: ${result.crossRuleAnalysis.priorityRecommendations}`)
    }
  }

  async getCacheStats(): Promise<any> {
    return intelligentQCCache.getCacheStats()
  }

  async getExecutionMetrics(): Promise<any> {
    return integratedQCEngine.getExecutionMetrics()
  }

  async demonstrateRuleManagement(): Promise<void> {
    console.log('\n🔧 Demonstrating Rule Management...')

    try {
      // 1. List all rules
      const allRules = await llmIntegratedRulesService.getEnhancedRules()
      console.log(`📋 Total rules in system: ${allRules.length}`)

      // 2. Filter rules by category
      const completenessRules = await llmIntegratedRulesService.getEnhancedRules({
        category: 'completeness'
      })
      console.log(`✅ Completeness rules: ${completenessRules.length}`)

      // 3. Test batch operations
      if (allRules.length > 0) {
        const ruleIds = allRules.slice(0, 2).map(r => r.id)
        console.log(`🔄 Testing batch disable for ${ruleIds.length} rules...`)
        
        const batchResult = await llmIntegratedRulesService.batchUpdateRuleStatus(
          ruleIds,
          false,
          'Demo batch disable test'
        )
        
        console.log(`✅ Batch operation: ${batchResult.successCount} success, ${batchResult.errorCount} errors`)

        // Re-enable them
        await llmIntegratedRulesService.batchUpdateRuleStatus(
          ruleIds,
          true,
          'Demo batch enable test'
        )
      }

      // 4. Demonstrate export/import
      if (allRules.length > 0) {
        console.log('📤 Testing configuration export...')
        const exportData = await llmIntegratedRulesService.exportRulesConfig(
          allRules.slice(0, 1).map(r => r.id)
        )
        console.log(`✅ Exported ${(exportData as { rules: unknown[] }).rules.length} rule configurations`)
      }

    } catch (error) {
      console.error('❌ Rule management demo failed:', error)
    }
  }

  async runFullDemo(): Promise<void> {
    console.log('🎯 Starting Full LLM QC Demo...\n')

    try {
      // 1. Initialize demo
      await this.initializeDemo()

      // 2. Demonstrate rule management
      await this.demonstrateRuleManagement()

      // 3. Run QC analysis
      const qcResult = await this.runQCDemo()

      // 4. Show performance metrics
      console.log('\n📊 Performance Metrics:')
      const cacheStats = await this.getCacheStats()
      console.log(`   Cache Hit Rate: ${(cacheStats.overall.hitRate * 100).toFixed(1)}%`)
      console.log(`   Total Cache Size: ${cacheStats.overall.cacheSize} entries`)

      const execMetrics = await this.getExecutionMetrics()
      console.log(`   Total Executions: ${execMetrics.totalExecutions}`)
      console.log(`   Success Rate: ${((execMetrics.successfulExecutions / execMetrics.totalExecutions) * 100).toFixed(1)}%`)
      console.log(`   Average Execution Time: ${execMetrics.averageExecutionTime.toFixed(0)}ms`)

      console.log('\n🎉 Full demo completed successfully!')
      return qcResult

    } catch (error: any) {
      console.error('❌ Full demo failed:', error)
      throw error
    }
  }
}

// Export singleton instance
export const llmQCDemoService = new LLMQCDemoService()
