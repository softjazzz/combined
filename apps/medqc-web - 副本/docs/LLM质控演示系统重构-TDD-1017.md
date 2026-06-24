# LLM 质控演示系统重构 - 技术设计文档 (TDD)

## 文档信息

| 项目 | 内容 |
|------|------|
| **文档版本** | v1.0 |
| **创建日期** | 2025-10-17 |
| **文档类型** | 技术设计文档 (Technical Design Document) |
| **项目名称** | LLM 质控演示系统重构 |
| **相关 PRD** | [LLM质控演示系统使用指南.md](./LLM质控演示系统使用指南.md) |

### 变更历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2025-10-17 | AI Agent | 初始版本，完整设计方案 |

---

## 1. 项目概述

### 1.1 背景与目标

**背景**：
- 当前 LLM 质控演示页面（`LLMQCDemoEnhanced.vue`）存在多个问题：
  - 演示控制面板被隐藏（`v-if="false"`）
  - 缺少通知列表管理界面（仅有模态框）
  - 缺少申诉列表管理界面（仅有模态框）
  - 规则参数配置功能不完整
  - 页面布局不够美观和高效
- 与 PRD 文档要求存在较大差距

**目标**：
1. 重构页面布局，采用 Ant Design 组件库打造美观、专业的界面
2. 恢复并优化演示控制面板，使其常驻可见
3. 新增通知列表管理界面（列表、筛选、排序、批量操作）
4. 新增申诉列表管理界面（列表、状态筛选、审核进度可视化）
5. 增强规则参数配置功能（权重、阈值、开关）
6. 100% 符合 PRD 文档的 5 个 Phase 要求

### 1.2 当前问题分析

| 问题类别 | 具体问题 | 影响程度 | 优先级 |
|---------|---------|---------|--------|
| **功能缺失** | 演示控制面板被隐藏 | 高 | P0 |
| **功能缺失** | 通知列表管理界面缺失 | 高 | P0 |
| **功能缺失** | 申诉列表管理界面缺失 | 高 | P0 |
| **功能不完整** | 规则参数配置不完整 | 中 | P1 |
| **用户体验** | 页面布局不够美观 | 中 | P1 |
| **代码质量** | 组件职责不清晰 | 低 | P2 |

### 1.3 重构范围

**包含范围**：
- ✅ 主页面布局重构（`LLMQCDemoEnhanced.vue`）
- ✅ 新建 8 个组件（控制面板、通知管理、申诉管理等）
- ✅ 修改 2 个现有组件（`QCRulesDemoPanel.vue` 等）
- ✅ 扩展 Store 方法（批量操作、筛选、参数管理）
- ✅ 优化样式和响应式布局

**不包含范围**：
- ❌ 后端 API 修改（保持现有接口不变）
- ❌ 核心业务逻辑修改（复用现有 Store 逻辑）
- ❌ 路由和权限系统修改
- ❌ 类型检查问题修复（`llmServiceNew` 缺失等）

### 1.4 预期收益

**功能完整性**：
- Phase 1-5 功能覆盖率从 70% 提升到 100%
- 新增通知管理和申诉管理完整功能

**用户体验**：
- 界面美观度提升 50%+（基于 Ant Design 设计规范）
- 操作效率提升 30%+（批量操作、快捷筛选）

**代码质量**：
- 组件职责更清晰，单一职责原则
- 代码可维护性提升 40%+

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    a-layout (整体布局)                        │
├─────────────────────────────────────────────────────────────┤
│  a-layout-header (顶部导航栏)                                 │
│  - 页面标题 + 面包屑导航                                       │
│  - 用户信息 + 通知徽标                                         │
├─────────────────────────────────────────────────────────────┤
│  a-layout-content (主内容区)                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ a-affix (固定控制栏)                                    │  │
│  │ DemoControlPanel - 演示控制面板                         │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────┬─────────────────────────────┐  │
│  │ a-col :span="17"        │ a-col :span="7"             │  │
│  │ (左侧主工作区 70%)       │ (右侧边栏 30%)               │  │
│  │                         │                             │  │
│  │ ┌─────────────────────┐ │ ┌─────────────────────────┐ │  │
│  │ │ a-steps             │ │ │ a-tabs                  │ │  │
│  │ │ 步骤指示器           │ │ │ ├─ 通知管理 (Badge)     │ │  │
│  │ └─────────────────────┘ │ │ └─ 申诉管理 (Badge)     │ │  │
│  │                         │ │                         │ │  │
│  │ ┌─────────────────────┐ │ │ NotificationManager     │ │  │
│  │ │ 步骤内容 (动态切换)  │ │ │ - 筛选器                │ │  │
│  │ │                     │ │ │ - 通知列表              │ │  │
│  │ │ Step 1: 测试对象选择│ │ │ - 批量操作              │ │  │
│  │ │ Step 2: 规则配置    │ │ │                         │ │  │
│  │ │ Step 3: 运行与结果  │ │ │ AppealManager           │ │  │
│  │ │                     │ │ │ - 状态筛选              │ │  │
│  │ └─────────────────────┘ │ │ - 申诉列表              │ │  │
│  │                         │ │ - 审核进度              │ │  │
│  └─────────────────────────┴─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  a-layout-footer (底部折叠区)                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ a-collapse (折叠面板)                                   │  │
│  │ ├─ 统计信息 (默认展开)                                  │  │
│  │ ├─ 演示日志 (默认折叠)                                  │  │
│  │ └─ 性能监控 (默认折叠)                                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 组件层级结构

```
LLMQCDemoEnhanced.vue (主页面)
├── DemoControlPanel.vue (演示控制面板) [新建]
├── a-row (主工作区 + 侧边栏)
│   ├── a-col (左侧 70%)
│   │   ├── StepNavigator.vue (步骤指示器) [新建]
│   │   └── 步骤内容 (动态组件)
│   │       ├── TargetSelectionStep.vue (测试对象选择) [新建]
│   │       ├── RulesConfigStep.vue (规则配置) [新建]
│   │       └── ResultAnalysisStep.vue (运行与结果) [新建]
│   └── a-col (右侧 30%)
│       └── a-tabs
│           ├── NotificationManager.vue (通知管理) [新建]
│           └── AppealManager.vue (申诉管理) [新建]
├── a-collapse (底部折叠区)
│   ├── StatisticsPanel.vue (统计面板) [复用]
│   ├── LogsPanel.vue (日志面板) [复用]
│   └── PerformancePanel.vue (性能监控) [复用]
└── 模态框组件
    ├── QCNotificationModal.vue (通知详情) [复用]
    ├── QCAppealModal.vue (申诉提交) [复用]
    ├── RuleParamsDrawer.vue (规则参数配置) [新建]
    └── RecordDocumentPicker.vue (病历选择器) [复用]
```

### 2.3 数据流设计

```
┌─────────────────────────────────────────────────────────┐
│                   useQCDemoStore (Pinia)                │
│  ┌───────────────────────────────────────────────────┐  │
│  │ State                                             │  │
│  │ - currentStep, isRunning, progress               │  │
│  │ - selectedRules, testRecord, analysisResult      │  │
│  │ - notifications, appeals                         │  │
│  │ - ruleParams (新增)                               │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Computed                                          │  │
│  │ - canStartDemo, unreadNotificationsCount         │  │
│  │ - pendingAppealsCount, averageQCScore            │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Actions                                           │  │
│  │ - startDemo, stopDemo, togglePause               │  │
│  │ - runQCAnalysis, handleNotificationAction        │  │
│  │ - batchMarkRead, batchIgnore (新增)              │  │
│  │ - updateRuleParams, getRuleParams (新增)         │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                    组件层 (Vue Components)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ControlPanel  │  │Notification  │  │AppealManager │  │
│  │              │  │Manager       │  │              │  │
│  │ - 读取状态   │  │ - 读取通知   │  │ - 读取申诉   │  │
│  │ - 调用操作   │  │ - 批量操作   │  │ - 筛选操作   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                    API 层 (ApiService)                   │
│  - analyzeRecord(recordId, rules)                       │
│  - getQCResult(recordId)                                │
│  - (其他 API 保持不变)                                   │
└─────────────────────────────────────────────────────────┘
```

**数据流向**：
1. **用户操作** → 组件事件处理 → Store Actions
2. **Store Actions** → 调用 API Service → 更新 State
3. **State 变化** → 触发 Computed 重新计算 → 组件响应式更新
4. **组件** → 读取 Store State/Computed → 渲染 UI

---

## 3. 详细设计

### 3.1 组件设计

#### 3.1.1 新建组件清单

| 组件名称 | 文件路径 | 职责 | 优先级 |
|---------|---------|------|--------|
| **DemoControlPanel.vue** | `components/demo/DemoControlPanel.vue` | 演示控制面板（开始/暂停/停止/重播 + 步骤导航） | P0 |
| **NotificationManager.vue** | `components/demo/NotificationManager.vue` | 通知列表管理（列表/筛选/排序/批量操作） | P0 |
| **AppealManager.vue** | `components/demo/AppealManager.vue` | 申诉列表管理（列表/状态筛选/审核进度） | P0 |
| **RulesConfigStep.vue** | `components/demo/RulesConfigStep.vue` | 规则配置步骤（规则选择 + 参数配置） | P1 |
| **TargetSelectionStep.vue** | `components/demo/TargetSelectionStep.vue` | 测试对象选择步骤（快速开始 + 手动选择） | P1 |
| **ResultAnalysisStep.vue** | `components/demo/ResultAnalysisStep.vue` | 运行与结果步骤（分析面板 + 结果展示） | P1 |
| **RuleParamsDrawer.vue** | `components/demo/RuleParamsDrawer.vue` | 规则参数配置抽屉 | P1 |
| **StepNavigator.vue** | `components/demo/StepNavigator.vue` | 步骤指示器与导航 | P2 |

#### 3.1.2 修改组件清单

| 组件名称 | 修改内容 | 优先级 |
|---------|---------|--------|
| **LLMQCDemoEnhanced.vue** | 重构页面布局，集成新组件，移除隐藏的控制面板 | P0 |
| **QCRulesDemoPanel.vue** | 增加参数配置入口，集成 RuleParamsDrawer | P1 |

#### 3.1.3 组件接口定义

##### DemoControlPanel.vue

```typescript
// Props
interface Props {
  // 无 Props，直接从 Store 读取状态
}

// Events
interface Emits {
  // 无 Events，直接调用 Store Actions
}

// 使用的 Store 状态
const demoStore = useQCDemoStore()
const {
  isRunning,
  isPaused,
  currentStep,
  canStartDemo,
  progress
} = storeToRefs(demoStore)

// 调用的 Store 方法
demoStore.startDemo()
demoStore.stopDemo()
demoStore.togglePause()
demoStore.replayDemo()
demoStore.previousStep()
demoStore.nextStep()
demoStore.jumpToStep(step)
```

##### NotificationManager.vue

```typescript
// Props
interface Props {
  // 无 Props，直接从 Store 读取
}

// Events
interface Emits {
  // 无 Events，直接调用 Store Actions
}

// 本地状态
const filters = ref({
  type: '',
  severity: '',
  status: ''
})
const selectedIds = ref<string[]>([])

// 使用的 Store 状态
const {
  notifications,
  unreadNotificationsCount
} = storeToRefs(demoStore)

// 计算属性
const filteredNotifications = computed(() => 
  demoStore.getFilteredNotifications(filters.value)
)

// 调用的 Store 方法
demoStore.batchMarkRead(ids)
demoStore.batchIgnore(ids)
demoStore.batchDelete(ids)
demoStore.handleNotificationAction(action, notification)
```

##### AppealManager.vue

```typescript
// Props
interface Props {
  // 无 Props
}

// 本地状态
const statusFilter = ref<AppealStatus | ''>('')
const selectedIds = ref<string[]>([])

// 使用的 Store 状态
const {
  appeals,
  pendingAppealsCount
} = storeToRefs(demoStore)

// 计算属性
const filteredAppeals = computed(() => 
  statusFilter.value 
    ? demoStore.getFilteredAppeals(statusFilter.value)
    : demoStore.appeals
)

// 调用的 Store 方法
demoStore.cancelAppeal(appealId)
demoStore.deleteAppeal(appealId)
```

##### RuleParamsDrawer.vue

```typescript
// Props
interface Props {
  visible: boolean
  rule: QualityControlRule | null
}

// Events
interface Emits {
  'update:visible': [value: boolean]
  'save': [params: RuleParams]
}

// 本地状态
const params = ref<RuleParams>({
  enabled: true,
  weight: 10,
  threshold: 0,
  severity: 'medium'
})

// 调用的 Store 方法
demoStore.updateRuleParams(ruleId, params)
demoStore.getRuleParams(ruleId)
demoStore.resetRuleParams(ruleId)
```

### 3.2 Store 扩展设计

#### 3.2.1 新增 State

```typescript
// 规则参数配置（新增）
const ruleParams = ref<Map<string, RuleParams>>(new Map())

// RuleParams 类型定义
interface RuleParams {
  enabled: boolean      // 是否启用
  weight: number        // 权重 (1-100)
  threshold?: number    // 阈值（可选）
  severity: 'low' | 'medium' | 'high' | 'critical'  // 严重程度
}
```

#### 3.2.2 新增 Computed

```typescript
// 无新增 Computed（现有的已足够）
```

#### 3.2.3 新增 Actions

```typescript
// 通知批量操作
function batchMarkRead(ids: string[]): void {
  ids.forEach(id => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.isRead = true
    }
  })
  message.success(`已标记 ${ids.length} 条通知为已读`)
}

function batchIgnore(ids: string[]): void {
  ids.forEach(id => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.status = 'ignored'
      notification.isRead = true
    }
  })
  message.success(`已忽略 ${ids.length} 条通知`)
}

function batchDelete(ids: string[]): void {
  notifications.value = notifications.value.filter(n => !ids.includes(n.id))
  message.success(`已删除 ${ids.length} 条通知`)
}

// 通知筛选
function getFilteredNotifications(filters: NotificationFilters): QCNotification[] {
  return notifications.value.filter(n => {
    if (filters.type && n.type !== filters.type) return false
    if (filters.severity && n.severity !== filters.severity) return false
    if (filters.status && n.status !== filters.status) return false
    return true
  })
}

// 申诉操作
function cancelAppeal(appealId: string): void {
  const appeal = appeals.value.find(a => a.id === appealId)
  if (appeal && appeal.status === 'pending') {
    appeal.status = 'cancelled'
    message.success('申诉已撤销')
  }
}

function deleteAppeal(appealId: string): void {
  appeals.value = appeals.value.filter(a => a.id !== appealId)
  message.success('申诉已删除')
}

// 申诉筛选
function getFilteredAppeals(status: AppealStatus): Appeal[] {
  return appeals.value.filter(a => a.status === status)
}

// 规则参数管理
function updateRuleParams(ruleId: string, params: RuleParams): void {
  ruleParams.value.set(ruleId, params)
  message.success('规则参数已更新')
}

function getRuleParams(ruleId: string): RuleParams | undefined {
  return ruleParams.value.get(ruleId)
}

function resetRuleParams(ruleId: string): void {
  ruleParams.value.delete(ruleId)
  message.success('规则参数已重置为默认值')
}
```

### 3.3 类型定义扩展

```typescript
// 通知筛选器类型
interface NotificationFilters {
  type?: 'error' | 'warning' | 'info' | 'success' | ''
  severity?: 'critical' | 'high' | 'medium' | 'low' | ''
  status?: 'pending' | 'confirmed' | 'ignored' | 'appealed' | ''
}

// 申诉状态类型
type AppealStatus = 'pending' | 'reviewing' | 'approved' | 'rejected' | 'cancelled'

// 规则参数类型
interface RuleParams {
  enabled: boolean
  weight: number
  threshold?: number
  severity: 'low' | 'medium' | 'high' | 'critical'
}
```

---

## 4. 实施计划

### 4.1 任务分解（WBS）

#### Phase 1: P0 核心功能（1-2 天）

**任务 1.1：创建演示控制面板**（4 小时）
- [ ] 创建 `DemoControlPanel.vue` 组件
- [ ] 实现开始/暂停/停止/重播按钮
- [ ] 实现步骤导航（上一步/下一步/下拉选择器）
- [ ] 集成进度显示和快捷操作菜单
- [ ] 集成到主页面顶部（使用 `a-affix`）

**任务 1.2：创建通知列表管理**（6 小时）
- [ ] 创建 `NotificationManager.vue` 组件
- [ ] 实现通知列表（使用 `a-list` 或 `a-table`）
- [ ] 实现筛选器（类型、严重程度、状态）
- [ ] 实现批量操作（标记已读、忽略、删除）
- [ ] 新增 Store 方法（`batchMarkRead`、`batchIgnore`、`batchDelete`、`getFilteredNotifications`）
- [ ] 集成到右侧边栏（使用 `a-tabs`）

**任务 1.3：创建申诉列表管理**（6 小时）
- [ ] 创建 `AppealManager.vue` 组件
- [ ] 实现申诉列表（使用 `a-table`）
- [ ] 实现状态筛选
- [ ] 实现审核进度可视化
- [ ] 新增 Store 方法（`cancelAppeal`、`deleteAppeal`、`getFilteredAppeals`）
- [ ] 集成到右侧边栏（使用 `a-tabs`）

**任务 1.4：重构主页面布局**（4 小时）
- [ ] 重构 `LLMQCDemoEnhanced.vue` 布局
- [ ] 使用 `a-layout` 组件替换现有布局
- [ ] 使用 `a-row` + `a-col` 实现左右布局（17:7 比例）
- [ ] 集成新组件（控制面板、通知管理、申诉管理）
- [ ] 移除隐藏的控制面板代码
- [ ] 调整样式和响应式布局

#### Phase 2: P1 重要功能（1 天）

**任务 2.1：创建规则参数配置**（4 小时）
- [ ] 创建 `RuleParamsDrawer.vue` 组件
- [ ] 实现参数表单（权重、阈值、开关、严重程度）
- [ ] 新增 Store 方法（`updateRuleParams`、`getRuleParams`、`resetRuleParams`）
- [ ] 新增 Store State（`ruleParams`）
- [ ] 集成到规则配置步骤

**任务 2.2：拆分步骤组件**（4 小时）
- [ ] 创建 `TargetSelectionStep.vue`
- [ ] 创建 `RulesConfigStep.vue`
- [ ] 创建 `ResultAnalysisStep.vue`
- [ ] 从主页面迁移逻辑到步骤组件
- [ ] 使用动态组件切换步骤内容

#### Phase 3: P2 优化项（0.5 天）

**任务 3.1：样式优化**（2 小时）
- [ ] 恢复被注释的样式
- [ ] 优化响应式布局（xs、sm、md、lg、xl）
- [ ] 添加过渡动画（步骤切换、列表项）
- [ ] 统一颜色和间距

**任务 3.2：步骤导航优化**（2 小时）
- [ ] 创建 `StepNavigator.vue`
- [ ] 优化步骤指示器样式
- [ ] 添加步骤间的过渡效果

### 4.2 时间估算

| Phase | 任务数 | 预计时间 | 累计时间 |
|-------|-------|---------|---------|
| Phase 1 (P0) | 4 | 20 小时 (2.5 天) | 2.5 天 |
| Phase 2 (P1) | 2 | 8 小时 (1 天) | 3.5 天 |
| Phase 3 (P2) | 2 | 4 小时 (0.5 天) | 4 天 |
| **总计** | **8** | **32 小时** | **4 天** |

**说明**：
- 以上时间为开发时间，不包括测试和修复 Bug 的时间
- 建议预留 1-2 天用于测试和优化
- 总项目周期：**5-6 天**

### 4.3 里程碑定义

| 里程碑 | 完成标志 | 预计日期 |
|-------|---------|---------|
| **M1: P0 功能完成** | 控制面板、通知管理、申诉管理、主页面布局重构完成 | Day 3 |
| **M2: P1 功能完成** | 规则参数配置、步骤组件拆分完成 | Day 4 |
| **M3: P2 优化完成** | 样式优化、步骤导航优化完成 | Day 5 |
| **M4: 测试与验收** | 所有功能测试通过，PRD 符合度 100% | Day 6 |

### 4.4 依赖关系

```
任务 1.1 (控制面板) ──┐
任务 1.2 (通知管理) ──┼──> 任务 1.4 (主页面重构) ──> 任务 2.2 (步骤拆分) ──> 任务 3.1 (样式优化)
任务 1.3 (申诉管理) ──┘                                                              ↓
                                                                                任务 3.2 (步骤导航)
任务 2.1 (规则参数) ──────────────────────────────────────────────────────────────────┘
```

**关键路径**：
1. 任务 1.1、1.2、1.3 → 任务 1.4 → 任务 2.2 → 任务 3.1 → 任务 3.2
2. 任务 2.1 可以并行开发

---

## 5. 验收标准

### 5.1 功能验收清单

#### Phase 1: 基础框架搭建

- [ ] **演示控制**
  - [ ] 开始演示按钮可用，点击后进入分析流程
  - [ ] 暂停/继续按钮可用，能正确暂停和恢复演示
  - [ ] 停止按钮可用，能终止演示并重置状态
  - [ ] 重播按钮可用，能重新开始演示
  - [ ] 步骤导航可用（上一步/下一步/下拉选择器）
  - [ ] 控制面板常驻可见（不被隐藏）

- [ ] **进度跟踪**
  - [ ] 实时显示分析进度（0% → 100%）
  - [ ] 步骤指示器正确显示当前步骤
  - [ ] 进度条颜色根据状态变化（正常/错误）

- [ ] **状态管理**
  - [ ] 演示状态自动保存到 localStorage
  - [ ] 页面刷新后能恢复演示状态
  - [ ] 清除状态功能可用

- [ ] **配置管理**
  - [ ] 导入演示状态功能可用
  - [ ] 导出演示状态功能可用
  - [ ] 演示配置模态框可用

#### Phase 2: 质控规则演示

- [ ] **规则选择**
  - [ ] 规则列表正确显示所有可用规则
  - [ ] 规则选择功能可用（多选）
  - [ ] 全选/清空功能可用
  - [ ] 规则参数配置功能可用（权重、阈值、开关）

- [ ] **分析过程**
  - [ ] 点击"开始分析"后正确触发分析流程
  - [ ] 分析步骤正确显示（准备数据 → 调用引擎 → 获取结果 → 生成通知）
  - [ ] 进度条正确推进（5% → 45% → 85% → 95% → 100%）

- [ ] **结果展示**
  - [ ] 分析完成后正确显示结果总结
  - [ ] 违规列表正确显示所有违规项
  - [ ] 空状态正确显示（无结果时）

#### Phase 3: 医生端通知模拟

- [ ] **通知接收**
  - [ ] 分析完成后自动生成通知
  - [ ] 通知列表正确显示所有通知
  - [ ] 未读通知数量正确显示

- [ ] **通知管理**
  - [ ] 筛选功能可用（类型、严重程度、状态）
  - [ ] 排序功能可用（时间、严重程度）
  - [ ] 分页功能可用
  - [ ] 批量操作可用（标记已读、忽略、删除）

- [ ] **详情查看**
  - [ ] 点击通知能打开详情模态框
  - [ ] 详情模态框正确显示完整信息
  - [ ] 确认/忽略/申诉操作可用

#### Phase 4: 申诉功能实现

- [ ] **申诉提交**
  - [ ] 申诉表单完整（类型、优先级、描述、附件）
  - [ ] 申诉提交成功后添加到申诉列表

- [ ] **申诉管理**
  - [ ] 申诉列表正确显示所有申诉
  - [ ] 状态筛选功能可用
  - [ ] 撤销/删除操作可用

- [ ] **审核流程**
  - [ ] 申诉提交后 5 秒开始审核
  - [ ] 审核中状态正确显示
  - [ ] 8 秒后审核完成，状态更新为已通过/已驳回
  - [ ] 审核通过率约 70%

- [ ] **结果反馈**
  - [ ] 审核完成后生成结果通知
  - [ ] 通知正确显示审核结果和评论

#### Phase 5: 系统整合和优化

- [ ] **数据持久化**
  - [ ] 演示状态保存到 localStorage
  - [ ] 页面刷新后能恢复状态

- [ ] **导入导出**
  - [ ] 导出功能生成正确的 JSON 文件
  - [ ] 导入功能能正确解析 JSON 文件

- [ ] **性能优化**
  - [ ] 响应式布局在不同屏幕尺寸下正常显示
  - [ ] 动画和过渡效果流畅
  - [ ] 列表滚动流畅（虚拟滚动）

- [ ] **用户体验**
  - [ ] 界面美观，符合 Ant Design 设计规范
  - [ ] 操作流畅，无明显卡顿
  - [ ] 错误提示友好，帮助用户理解问题

### 5.2 非功能性验收标准

#### 性能标准
- [ ] 页面首次加载时间 < 2 秒
- [ ] 步骤切换响应时间 < 200ms
- [ ] 列表筛选响应时间 < 100ms
- [ ] 批量操作（100 条）响应时间 < 500ms

#### 兼容性标准
- [ ] 支持 Chrome 90+
- [ ] 支持 Firefox 88+
- [ ] 支持 Safari 14+
- [ ] 支持 Edge 90+
- [ ] 响应式布局支持屏幕宽度 >= 1024px

#### 代码质量标准
- [ ] TypeScript 类型检查通过（无 `any` 类型）
- [ ] ESLint 检查通过（无错误）
- [ ] 组件单一职责，代码行数 < 500 行
- [ ] 关键函数有注释说明

---

## 附录

### A. 术语表

| 术语 | 说明 |
|------|------|
| **PRD** | Product Requirements Document，产品需求文档 |
| **TDD** | Technical Design Document，技术设计文档 |
| **Store** | Pinia 状态管理库的数据存储 |
| **Ant Design** | 企业级 UI 设计语言和 Vue 组件库 |
| **响应式布局** | 根据屏幕尺寸自动调整布局的设计方式 |
| **虚拟滚动** | 只渲染可见区域的列表项，提升大列表性能 |

### B. 参考文档

- [LLM质控演示系统使用指南.md](./LLM质控演示系统使用指南.md) - PRD 文档
- [Ant Design Vue 官方文档](https://antdv.com/components/overview-cn)
- [Pinia 官方文档](https://pinia.vuejs.org/)
- [Vue 3 官方文档](https://cn.vuejs.org/)

### C. 相关链接

- 项目仓库：`health-qc-monorepo`
- 主页面路径：`apps/medqc-web/src/views/demo/LLMQCDemoEnhanced.vue`
- Store 路径：`apps/medqc-web/src/stores/qcDemo.ts`
- 组件目录：`apps/medqc-web/src/components/demo/`

---

**文档结束**

