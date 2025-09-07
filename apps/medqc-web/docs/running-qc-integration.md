# 运行病历质控功能集成指南

## 📋 概述

运行病历质控功能专门处理**在院病人**的实时质控，与终末质控（出院后归档病历质控）形成完整的质控体系。

## 🏗️ 系统架构

### 核心区别

| 功能类型 | 运行病历质控 | 终末质控 |
|---------|-------------|----------|
| **对象** | 在院病人 | 出院病人 |
| **时机** | 实时/定时 | 归档后 |
| **目的** | 预防和及时纠正 | 总结和评价 |
| **频率** | 持续监控 | 一次性 |
| **重点** | 时效性、完整性 | 全面性、规范性 |

### 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    运行病历质控系统                          │
├─────────────────────────────────────────────────────────────┤
│  前端界面层                                                 │
│  ├── RunningQCDashboard.vue    # 在院病人仪表板             │
│  ├── RunningQCResult.vue       # 质控结果展示               │
│  └── RunningQCAlerts.vue       # 实时提醒组件               │
├─────────────────────────────────────────────────────────────┤
│  业务逻辑层                                                 │
│  ├── running-qc-service.ts     # 运行质控服务               │
│  ├── quality-standards-loader.ts # 质控标准加载器           │
│  └── notification-service.ts   # 通知服务                   │
├─────────────────────────────────────────────────────────────┤
│  数据存储层                                                 │
│  ├── quality-standards.json    # 质控标准数据               │
│  ├── running_qc_results        # 运行质控结果               │
│  └── qc_alerts                 # 质控提醒记录               │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 核心功能

### 1. 实时质控监控

**功能特点**：
- ✅ 基于CSV质控标准的实时检查
- ✅ 科室特定规则应用
- ✅ 时效性自动监控
- ✅ 风险等级自动评估

**检查类型**：
```typescript
interface QCCheckTypes {
  realTime: {
    name: '实时检查'
    trigger: '病历内容变更时'
    rules: ['完整性', '一致性', '合规性']
  }
  scheduled: {
    name: '定时检查'
    trigger: '每2-24小时'
    rules: ['时效性', '进展性']
  }
  triggered: {
    name: '事件触发'
    trigger: '特定医疗事件'
    rules: ['手术记录', '出院准备']
  }
}
```

### 2. 质控标准应用

**基于CSV数据**：
- 📊 234个质控内容
- 🏥 6个评分项目组
- 🔍 科室特定规则筛选
- ⚡ 启用状态动态控制

**规则应用逻辑**：
```typescript
// 1. 获取科室适用规则
const applicableRules = qualityStandards.filter(std => 
  std.departments.some(dept => dept.includes(currentDepartment))
)

// 2. 检查启用状态
const enabledRules = applicableRules.filter(rule => rule.isEnabled)

// 3. 应用医生端规则
const doctorRules = enabledRules.filter(rule => rule.isEffectiveToDoctor)
```

### 3. 时效性监控

**关键时间节点**：
- 📝 入院记录：24小时内
- 📋 首次病程记录：8小时内
- 🔄 日常病程记录：24小时内
- 🏥 出院记录：24小时内

**监控实现**：
```typescript
// 时效性检查示例
const timelinessChecks = [
  {
    checkType: 'admission_record',
    timeLimit: 24, // 小时
    description: '入院记录应在入院后24小时内完成'
  },
  {
    checkType: 'progress_note',
    timeLimit: 8, // 小时
    description: '首次病程记录应在入院后8小时内完成'
  }
]
```

### 4. 风险等级评估

**风险分级**：
```typescript
interface RiskLevels {
  low: {
    color: 'green'
    nextCheck: '24小时'
    description: '质控正常，按常规检查'
  }
  medium: {
    color: 'orange'
    nextCheck: '12小时'
    description: '存在一般问题，需要关注'
  }
  high: {
    color: 'red'
    nextCheck: '6小时'
    description: '存在重要问题，需要及时处理'
  }
  critical: {
    color: 'red'
    nextCheck: '2小时'
    description: '存在严重问题，需要立即处理'
  }
}
```

## 🔧 集成步骤

### Step 1: 导入运行质控服务

```typescript
// 在需要的页面中导入
import { runningQCService } from '@/lib/running-qc-service'
import type { RunningQCRequest, RunningQCResult } from '@/lib/running-qc-service'
```

### Step 2: 执行运行质控分析

```typescript
// 分析在院病人
const analyzeInpatient = async (patient: InpatientRecord) => {
  const request: RunningQCRequest = {
    recordId: `running-${patient.id}`,
    patientId: patient.id,
    content: patient.medicalContent,
    department: patient.department,
    admissionDate: patient.admissionDate,
    currentDate: new Date().toISOString(),
    doctorId: patient.doctorId,
    analysisType: 'real-time'
  }
  
  const result = await runningQCService.analyzeRunningRecord(request)
  return result
}
```

### Step 3: 集成仪表板组件

```vue
<template>
  <div class="medical-dashboard">
    <!-- 添加运行质控仪表板 -->
    <running-qc-dashboard />
  </div>
</template>

<script setup lang="ts">
import RunningQCDashboard from '@/components/running-qc/RunningQCDashboard.vue'
</script>
```

### Step 4: 配置路由

```typescript
// router/index.ts
const routes = [
  {
    path: '/running-qc',
    name: 'RunningQC',
    component: () => import('@/views/RunningQCView.vue'),
    meta: { 
      title: '运行病历质控',
      requiresAuth: true,
      roles: ['admin', 'qc_manager', 'doctor']
    }
  }
]
```

## 📊 使用示例

### 1. 基础使用

```typescript
import { runningQCService } from '@/lib/running-qc-service'

// 分析单个病人
const result = await runningQCService.analyzeRunningRecord({
  recordId: 'REC001',
  patientId: 'PAT001',
  content: '病历内容...',
  department: '内一科',
  admissionDate: '2024-01-15T10:00:00Z',
  currentDate: '2024-01-18T14:30:00Z',
  doctorId: 'DOC001',
  analysisType: 'real-time'
})

console.log('质控结果:', result)
```

### 2. 批量分析

```typescript
// 批量分析科室所有在院病人
const analyzeDepartmentPatients = async (department: string) => {
  const patients = await getInpatientsByDepartment(department)
  const results = []
  
  for (const patient of patients) {
    try {
      const result = await runningQCService.analyzeRunningRecord({
        recordId: `running-${patient.id}`,
        patientId: patient.id,
        content: patient.medicalContent,
        department: patient.department,
        admissionDate: patient.admissionDate,
        currentDate: new Date().toISOString(),
        doctorId: patient.doctorId,
        analysisType: 'scheduled'
      })
      results.push(result)
    } catch (error) {
      console.error(`分析患者${patient.id}失败:`, error)
    }
  }
  
  return results
}
```

### 3. 定时任务集成

```typescript
// 设置定时质控检查
const setupScheduledQC = () => {
  // 每2小时执行一次高风险病人检查
  setInterval(async () => {
    const highRiskPatients = await getHighRiskPatients()
    for (const patient of highRiskPatients) {
      await runningQCService.analyzeRunningRecord({
        recordId: `scheduled-${patient.id}`,
        patientId: patient.id,
        content: patient.medicalContent,
        department: patient.department,
        admissionDate: patient.admissionDate,
        currentDate: new Date().toISOString(),
        doctorId: patient.doctorId,
        analysisType: 'scheduled'
      })
    }
  }, 2 * 60 * 60 * 1000) // 2小时
}
```

## 🔔 提醒和通知

### 1. 实时提醒

```typescript
// 监听质控结果，发送实时提醒
const handleQCResult = (result: RunningQCResult) => {
  if (result.summary.riskLevel === 'critical') {
    // 发送紧急提醒
    sendUrgentNotification({
      title: '质控紧急提醒',
      message: `患者${result.patientId}存在严重质控问题`,
      recipient: result.doctorId,
      type: 'urgent'
    })
  }
  
  // 检查超时问题
  const overdueChecks = result.timelinessChecks.filter(check => check.isOverdue)
  if (overdueChecks.length > 0) {
    sendTimelinessAlert({
      patientId: result.patientId,
      overdueItems: overdueChecks,
      recipient: result.doctorId
    })
  }
}
```

### 2. 科室汇总提醒

```typescript
// 每日科室质控汇总
const sendDepartmentSummary = async (department: string) => {
  const patients = await getInpatientsByDepartment(department)
  const summary = {
    totalPatients: patients.length,
    highRiskCount: 0,
    overdueCount: 0,
    avgScore: 0
  }
  
  for (const patient of patients) {
    const result = await getLatestQCResult(patient.id)
    if (result) {
      if (result.summary.riskLevel === 'high' || result.summary.riskLevel === 'critical') {
        summary.highRiskCount++
      }
      if (result.timelinessChecks.some(check => check.isOverdue)) {
        summary.overdueCount++
      }
      summary.avgScore += result.summary.totalScore
    }
  }
  
  summary.avgScore = summary.avgScore / patients.length
  
  // 发送科室汇总
  sendDepartmentReport(department, summary)
}
```

## 📈 性能优化

### 1. 缓存策略

```typescript
// 质控结果缓存
const qcResultCache = new Map<string, RunningQCResult>()

const getCachedResult = (patientId: string): RunningQCResult | null => {
  const cached = qcResultCache.get(patientId)
  if (cached && isResultValid(cached)) {
    return cached
  }
  return null
}

const cacheResult = (result: RunningQCResult) => {
  qcResultCache.set(result.patientId, result)
  // 设置过期时间
  setTimeout(() => {
    qcResultCache.delete(result.patientId)
  }, 30 * 60 * 1000) // 30分钟过期
}
```

### 2. 批量处理

```typescript
// 批量处理优化
const batchAnalyzePatients = async (patients: InpatientRecord[]) => {
  const BATCH_SIZE = 10
  const results = []
  
  for (let i = 0; i < patients.length; i += BATCH_SIZE) {
    const batch = patients.slice(i, i + BATCH_SIZE)
    const batchPromises = batch.map(patient => 
      runningQCService.analyzeRunningRecord({
        recordId: `batch-${patient.id}`,
        patientId: patient.id,
        content: patient.medicalContent,
        department: patient.department,
        admissionDate: patient.admissionDate,
        currentDate: new Date().toISOString(),
        doctorId: patient.doctorId,
        analysisType: 'scheduled'
      })
    )
    
    const batchResults = await Promise.allSettled(batchPromises)
    results.push(...batchResults)
    
    // 批次间延迟，避免过载
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  
  return results
}
```

## 🛠️ 数据库扩展

### 创建运行质控结果表

```sql
-- 创建运行质控结果表
CREATE TABLE running_qc_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id VARCHAR(100) NOT NULL,
  patient_id VARCHAR(100) NOT NULL,
  analysis_type VARCHAR(20) NOT NULL, -- 'real-time', 'scheduled', 'triggered'
  total_score INTEGER NOT NULL,
  grade VARCHAR(10) NOT NULL, -- '甲级', '乙级', '丙级'
  risk_level VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
  real_time_issues JSONB,
  department_issues JSONB,
  timeliness_checks JSONB,
  recommendations TEXT[],
  next_check_time TIMESTAMP WITH TIME ZONE,
  analysis_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_running_qc_patient_id ON running_qc_results(patient_id);
CREATE INDEX idx_running_qc_risk_level ON running_qc_results(risk_level);
CREATE INDEX idx_running_qc_analysis_time ON running_qc_results(analysis_time);
CREATE INDEX idx_running_qc_next_check ON running_qc_results(next_check_time);

-- 创建质控提醒表
CREATE TABLE qc_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id VARCHAR(100) NOT NULL,
  alert_type VARCHAR(50) NOT NULL, -- 'timeliness', 'quality', 'critical'
  severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
  title VARCHAR(200) NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN DEFAULT FALSE,
  is_handled BOOLEAN DEFAULT FALSE,
  assigned_to VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  handled_at TIMESTAMP WITH TIME ZONE
);

-- 创建索引
CREATE INDEX idx_qc_alerts_patient_id ON qc_alerts(patient_id);
CREATE INDEX idx_qc_alerts_severity ON qc_alerts(severity);
CREATE INDEX idx_qc_alerts_unread ON qc_alerts(is_read) WHERE is_read = FALSE;
```

## 🎯 最佳实践

### 1. 分析频率建议

```typescript
const analysisSchedule = {
  // 新入院患者（24小时内）
  newAdmission: {
    frequency: '每2小时',
    focus: ['入院记录', '首次病程记录']
  },
  
  // 普通住院患者
  regular: {
    frequency: '每12小时',
    focus: ['病程记录', '医嘱执行']
  },
  
  // 高风险患者
  highRisk: {
    frequency: '每6小时',
    focus: ['全面检查', '时效性监控']
  },
  
  // 即将出院患者
  preDischarge: {
    frequency: '每4小时',
    focus: ['出院准备', '记录完整性']
  }
}
```

### 2. 错误处理

```typescript
const robustAnalysis = async (request: RunningQCRequest) => {
  try {
    return await runningQCService.analyzeRunningRecord(request)
  } catch (error) {
    console.error('运行质控分析失败:', error)
    
    // 降级处理
    return {
      recordId: request.recordId,
      patientId: request.patientId,
      analysisType: request.analysisType,
      analysisTime: new Date().toISOString(),
      summary: {
        totalScore: 0,
        grade: '丙级' as const,
        overallAssessment: '分析服务暂时不可用',
        riskLevel: 'medium' as const
      },
      realTimeIssues: [],
      departmentSpecificIssues: [],
      timelinessChecks: [],
      recommendations: ['建议稍后重试质控分析'],
      nextCheckTime: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()
    }
  }
}
```

## 📝 总结

运行病历质控功能通过以下方式提升医疗质量：

1. **实时监控**：及时发现和纠正问题
2. **科室适配**：基于CSV标准的个性化规则
3. **时效管理**：自动监控关键时间节点
4. **风险预警**：分级提醒和处理机制
5. **数据驱动**：基于234个质控标准的精准分析

这个功能与现有的终末质控形成互补，构建了完整的医疗质控体系。 