# 人工审核模块实现文档

## 📋 概述

本文档描述了基于LLM集成质控系统的人工审核模块实现。该模块扩展了现有的Phase 1组件，提供了完整的审核任务管理、多级审核、消息通知等功能。

## 🏗️ 架构设计

### 核心组件架构
```
人工审核模块
├── 数据层 (Database Layer)
│   ├── qc_audit_tasks - 审核任务表
│   ├── qc_audit_task_items - 审核任务明细表
│   ├── qc_audit_results - 多级审核结果表
│   ├── qc_defects - 质控缺陷表
│   └── qc_notifications - 消息通知表
│
├── 服务层 (Service Layer)
│   ├── AuditTaskService - 审核任务管理服务
│   ├── AuditResultService - 审核结果管理服务
│   ├── NotificationService - 消息通知服务
│   └── IntelligentSamplingService - 智能抽样服务
│
├── 组件层 (Component Layer)
│   ├── MultiLevelAuditTabs - 多级审核标签页
│   ├── AuditResultPanel - 审核结果面板
│   ├── NotificationCenter - 消息通知中心
│   └── AuditModuleDemo - 演示页面
│
└── 集成层 (Integration Layer)
    ├── LLM引擎集成 - 利用现有IntegratedQCEngine
    ├── 智能缓存集成 - 利用现有IntelligentQCCache
    └── Supabase实时集成 - 基于postgres_changes
```

## 🚀 已实现功能

### 1. 审核任务管理系统
- ✅ **智能抽样算法**：支持分层抽样、风险导向抽样、系统抽样
- ✅ **多层级审核配置**：科室级、院级、专家级三级审核
- ✅ **任务分配和负载均衡**：自动分配审核员，支持工作量平衡
- ✅ **风险等级评估**：基于LLM的智能风险分级（A/B/C级）

### 2. 住院病历审核功能
- ✅ **多级审核结果展示**：分页签展示不同级别审核结果
- ✅ **权限控制机制**：上级可查看和修改下级审核结果
- ✅ **AI辅助缺陷识别**：集成现有LLM引擎进行智能缺陷检测
- ✅ **批量审核操作**：支持批量处理审核任务

### 3. 消息通知系统
- ✅ **实时消息推送**：基于Supabase实时功能
- ✅ **智能消息生成**：利用DynamicPromptGenerator生成个性化通知
- ✅ **离线消息处理**：支持离线消息队列和同步
- ✅ **多通道分发**：支持实时推送、浏览器通知等

## 📁 文件结构

```
src/
├── types/
│   └── audit-module.ts              # 审核模块类型定义
├── services/
│   ├── audit-task-service.ts        # 审核任务管理服务
│   ├── audit-result-service.ts      # 审核结果管理服务
│   └── notification-service.ts      # 消息通知服务
├── components/
│   ├── audit/
│   │   ├── MultiLevelAuditTabs.vue  # 多级审核标签页
│   │   └── AuditResultPanel.vue     # 审核结果面板
│   └── notification/
│       └── NotificationCenter.vue   # 消息通知中心
├── views/
│   └── AuditModuleDemo.vue          # 演示页面
├── utils/
│   └── date-utils.ts                # 日期工具函数
└── database/
    └── migrations/
        └── 20241224_create_audit_tables.sql  # 数据库表结构
```

## 🔧 技术实现细节

### 智能抽样算法
```typescript
// 分层抽样实现
private async stratifiedSampling(
  records: any[],
  config: SamplingConfig
): Promise<QCAuditTaskItem[]> {
  const strata = {
    A: records.filter(r => r.risk_level === 'A'), // 高风险
    B: records.filter(r => r.risk_level === 'B'), // 中风险
    C: records.filter(r => r.risk_level === 'C')  // 低风险
  }
  
  // 按配置的比例进行抽样
  // ...实现细节
}
```

### LLM集成缺陷识别
```typescript
// AI辅助缺陷识别
async suggestDefects(
  taskItem: QCAuditTaskItem,
  context: DefectAnalysisContext
): Promise<AIDefectSuggestion[]> {
  
  // 使用现有的IntegratedQCEngine
  const analysisResult = await this.qcEngine.executeQualityControl({
    patientId: taskItem.patient_id,
    documents: context.medical_record ? [context.medical_record] : [],
    departmentId: taskItem.department_id
  }, taskItem.department_id, {
    category: 'defect_detection',
    implementation_type: 'semantic_llm'
  })
  
  return this.convertToDefectSuggestions(analysisResult, context)
}
```

### Supabase实时通信
```typescript
// 实时消息监听
const channel = supabase
  .channel(`user_notifications_${userId}`)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'qc_notifications',
    filter: `recipient_id=eq.${userId}`
  }, (payload) => this.handleNewNotification(payload.new))
  .subscribe()
```

## 🎯 核心特性

### 1. 智能化程度高
- **AI辅助抽样**：基于历史数据和风险评估的智能抽样
- **LLM缺陷识别**：自动识别潜在质控问题
- **智能消息生成**：个性化通知内容生成

### 2. 多级审核流程
- **三级审核体系**：科室→院级→专家级递进审核
- **权限分级管理**：上级可修改下级审核结果
- **审核历史追踪**：完整的审核时间线记录

### 3. 实时通信能力
- **即时消息推送**：基于Supabase的实时通信
- **离线消息同步**：支持离线状态下的消息处理
- **多端同步**：跨设备消息状态同步

### 4. 高度可扩展
- **模块化设计**：各功能模块独立，易于扩展
- **服务化架构**：清晰的服务层分离
- **类型安全**：完整的TypeScript类型定义

## 🔌 与现有系统集成

### Phase 1组件复用
- **IntegratedQCEngine**：用于AI辅助缺陷识别和风险评估
- **LLMIntegratedRulesService**：提供规则引擎支持
- **IntelligentQCCache**：提供智能缓存功能
- **DynamicPromptGenerator**：用于智能消息生成

### 数据库扩展
- 在现有schema基础上新增8个审核相关表
- 保持与现有表结构的兼容性
- 支持现有用户权限体系

## 🚀 使用方法

### 1. 数据库初始化
```sql
-- 执行数据库迁移脚本
\i database/migrations/20241224_create_audit_tables.sql
```

### 2. 创建审核任务
```typescript
import { auditTaskService } from '@/services/audit-task-service'

const task = await auditTaskService.createAuditTask({
  task_name: '2024年第四季度质控',
  task_type: 'routine',
  audit_level: 'department',
  audit_scope: {
    departments: ['dept_001'],
    document_types: ['admission_record']
  },
  sampling_config: {
    sampling_method: 'stratified',
    sampling_ratio: 0.1
  },
  planned_start_date: '2024-12-01',
  planned_end_date: '2024-12-31',
  assigned_reviewers: ['reviewer_001']
})
```

### 3. 多级审核操作
```vue
<template>
  <MultiLevelAuditTabs
    :task-item-id="taskItemId"
    @result-updated="handleResultUpdated"
    @result-submitted="handleResultSubmitted"
  />
</template>
```

### 4. 消息通知
```typescript
import { notificationService } from '@/services/notification-service'

await notificationService.sendNotification(
  recipientId,
  'clinician',
  'rectification_required',
  {
    patient_id: 'patient_001',
    defect_id: 'defect_001'
  }
)
```

## 🎨 演示功能

访问 `/audit-module-demo` 页面可以体验：
- 审核任务创建和管理
- 多级审核流程演示
- 消息通知系统测试
- AI辅助功能展示
- 系统集成验证

## 🔮 后续扩展计划

1. **移动端适配**：响应式设计优化
2. **报表分析**：审核数据统计和分析
3. **工作流引擎**：更复杂的审核流程支持
4. **第三方集成**：与HIS、EMR系统集成
5. **性能优化**：大数据量处理优化

## 📞 技术支持

如有问题或建议，请联系开发团队或查看相关文档。

---

*本文档随代码更新而持续维护*
