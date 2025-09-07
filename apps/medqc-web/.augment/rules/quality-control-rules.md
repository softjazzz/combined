---
title: "质控规则管理规范"
description: "医疗质控规则的创建、管理和执行标准"
version: "2.0"
category: "business"
priority: "critical"
type: "manual"
---
# 质控规则管理规范

## 🎯 质控规则体系

### 1. 规则编码标准
```
格式: X.Y.Z
X: 主分类 (1-完整性, 2-一致性, 3-合理性, 4-及时性)
Y: 子分类 (01-99)
Z: 具体规则 (01-99)

示例:
1.01.01 - 患者基本信息完整性检查
2.03.05 - 诊断与用药一致性检查
3.02.10 - 手术适应症合理性评估
4.01.03 - 病历书写及时性检查
```

### 2. 规则分类体系

#### 完整性规则 (Completeness - 1.x.x)
检查病历记录的完整性，确保必要信息不缺失。

```typescript
// 完整性规则示例
const completenessRule: QCRule = {
  ruleCode: '1.01.01',
  name: '患者基本信息完整性检查',
  category: 'completeness',
  ruleType: 'objective',
  severity: 'critical',
  maxScore: 0, // 单否项
  weight: 5.0,
  checkLogic: {
    type: 'field_validation',
    requiredFields: ['patient_name', 'gender', 'age', 'admission_date'],
    validationRules: {
      patient_name: { minLength: 2, maxLength: 50 },
      age: { min: 0, max: 150, type: 'integer' }
    }
  }
}
```

#### 一致性规则 (Consistency - 2.x.x)
检查病历内容的一致性，确保信息前后呼应。

```typescript
// 一致性规则示例
const consistencyRule: QCRule = {
  ruleCode: '2.01.01',
  name: '入院诊断与出院诊断一致性',
  category: 'consistency',
  ruleType: 'hybrid',
  severity: 'major',
  maxScore: 15,
  weight: 3.0,
  checkLogic: {
    type: 'cross_field_validation',
    fields: ['admission_diagnosis', 'discharge_diagnosis'],
    validationType: 'diagnosis_consistency'
  },
  promptTemplate: `
请分析以下病历的诊断一致性：
入院诊断：{admission_diagnosis}
出院诊断：{discharge_diagnosis}

请评估：
1. 诊断是否存在逻辑矛盾
2. 诊断变化是否合理
3. 是否需要补充说明
`
}
```

#### 合理性规则 (Rationality - 3.x.x)
检查医疗决策和治疗方案的合理性。

```typescript
// 合理性规则示例
const rationalityRule: QCRule = {
  ruleCode: '3.01.01',
  name: '用药合理性评估',
  category: 'rationality',
  ruleType: 'subjective',
  severity: 'major',
  maxScore: 20,
  weight: 4.0,
  promptTemplate: `
请评估以下用药方案的合理性：
患者信息：年龄{age}岁，性别{gender}
诊断：{diagnosis}
用药：{medications}
过敏史：{allergies}

请从以下角度评估：
1. 药物选择是否适当
2. 剂量是否合理
3. 是否存在药物相互作用
4. 是否考虑了患者特殊情况
`
}
```

#### 及时性规则 (Timeliness - 4.x.x)
检查医疗活动的时效性要求。

```typescript
// 及时性规则示例
const timelinessRule: QCRule = {
  ruleCode: '4.01.01',
  name: '入院记录书写及时性',
  category: 'timeliness',
  ruleType: 'objective',
  severity: 'minor',
  maxScore: 5,
  weight: 1.0,
  checkLogic: {
    type: 'time_validation',
    timeFields: ['admission_time', 'record_creation_time'],
    maxInterval: '24 hours',
    businessRules: {
      excludeWeekends: false,
      excludeHolidays: false
    }
  }
}
```

## 🔧 规则配置管理

### 1. 规则配置接口
```typescript
// types/qc-rule.ts
export interface QCRule {
  id: string
  ruleCode: string
  name: string
  description?: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  ruleType: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  maxScore: number
  weight: number
  checkLogic?: CheckLogicConfig
  promptTemplate?: string
  isActive: boolean
  version: number
  createdAt: Date
  updatedAt: Date
}

export interface CheckLogicConfig {
  type: 'field_validation' | 'cross_field_validation' | 'time_validation' | 'custom'
  [key: string]: any
}
```

### 2. 规则执行引擎
```typescript
// services/qc-rules-engine.ts
export class QCRulesEngine {
  async executeRule(rule: QCRule, medicalRecord: MedicalRecord): Promise<QCResult> {
    try {
      switch (rule.ruleType) {
        case 'objective':
          return await this.executeObjectiveRule(rule, medicalRecord)
        case 'subjective':
          return await this.executeSubjectiveRule(rule, medicalRecord)
        case 'hybrid':
          return await this.executeHybridRule(rule, medicalRecord)
        default:
          throw new Error(`不支持的规则类型: ${rule.ruleType}`)
      }
    } catch (error) {
      console.error(`规则执行失败 [${rule.ruleCode}]:`, error)
      return {
        ruleId: rule.id,
        ruleCode: rule.ruleCode,
        status: 'error',
        score: 0,
        message: '规则执行异常',
        executedAt: new Date()
      }
    }
  }

  private async executeObjectiveRule(rule: QCRule, record: MedicalRecord): Promise<QCResult> {
    // 客观规则执行逻辑
    const validator = new ObjectiveRuleValidator(rule.checkLogic)
    const isValid = await validator.validate(record)
    
    return {
      ruleId: rule.id,
      ruleCode: rule.ruleCode,
      status: isValid ? 'pass' : 'fail',
      score: isValid ? 0 : rule.maxScore,
      message: isValid ? '检查通过' : validator.getErrorMessage(),
      executedAt: new Date()
    }
  }

  private async executeSubjectiveRule(rule: QCRule, record: MedicalRecord): Promise<QCResult> {
    // 主观规则执行逻辑 - 调用AI分析
    const aiAnalyzer = new AIQualityAnalyzer()
    const prompt = this.buildPrompt(rule.promptTemplate!, record)
    const analysis = await aiAnalyzer.analyze(prompt)
    
    return {
      ruleId: rule.id,
      ruleCode: rule.ruleCode,
      status: analysis.score === 0 ? 'pass' : 'fail',
      score: analysis.score,
      message: analysis.message,
      suggestions: analysis.suggestions,
      executedAt: new Date()
    }
  }
}
```

### 3. 规则管理界面规范
```vue
<!-- views/rules/QCRulesManagement.vue -->
<template>
  <div class="qc-rules-management">
    <!-- 规则列表 -->
    <QCRulesList 
      :rules="rules"
      :loading="loading"
      @edit="handleEditRule"
      @delete="handleDeleteRule"
      @toggle-status="handleToggleStatus"
    />
    
    <!-- 规则编辑器 -->
    <QCRuleEditor
      v-if="showEditor"
      :rule="currentRule"
      @save="handleSaveRule"
      @cancel="handleCancelEdit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useQCRulesStore } from '@/stores/qc-rules'
import type { QCRule } from '@/types/qc-rule'

const qcRulesStore = useQCRulesStore()
const rules = computed(() => qcRulesStore.rules)
const loading = ref(false)
const showEditor = ref(false)
const currentRule = ref<QCRule | null>(null)

const handleEditRule = (rule: QCRule) => {
  currentRule.value = rule
  showEditor.value = true
}

const handleSaveRule = async (rule: QCRule) => {
  try {
    await qcRulesStore.saveRule(rule)
    showEditor.value = false
    showSuccess('规则保存成功')
  } catch (error) {
    showError('规则保存失败')
  }
}

onMounted(() => {
  qcRulesStore.fetchRules()
})
</script>
```

## 📊 质控结果管理

### 1. 质控结果数据结构
```typescript
export interface QCResult {
  id: string
  medicalRecordId: string
  ruleId: string
  ruleCode: string
  status: 'pass' | 'fail' | 'warning' | 'error'
  score: number
  message: string
  suggestions?: string[]
  executedAt: Date
  reviewedAt?: Date
  reviewedBy?: string
  reviewComments?: string
}

export interface QCReport {
  medicalRecordId: string
  totalScore: number
  maxPossibleScore: number
  qualityGrade: 'A' | 'B' | 'C' | 'D'
  results: QCResult[]
  summary: {
    totalRules: number
    passedRules: number
    failedRules: number
    warningRules: number
    errorRules: number
  }
  generatedAt: Date
}
```

## 🚨 质控规则开发注意事项

1. **规则编码唯一性**: 确保规则编码在系统中唯一
2. **版本管理**: 规则修改时需要更新版本号
3. **向后兼容**: 规则修改不应影响历史数据分析
4. **性能考虑**: 避免创建执行时间过长的规则
5. **错误处理**: 规则执行失败不应影响整体质控流程

## 📋 质控规则审查清单
- [ ] 规则编码符合标准格式
- [ ] 规则分类正确
- [ ] 严重程度设置合理
- [ ] 扣分标准明确
- [ ] 检查逻辑完整
- [ ] AI提示模板清晰
- [ ] 包含适当的错误处理
- [ ] 性能测试通过