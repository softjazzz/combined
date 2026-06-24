# LLM 质控演示模块 - PRD 对比分析与优化方案

**文档类型**: 技术分析与实施方案  
**版本**: v1.0  
**创建日期**: 2025-10-15  
**分析对象**: LLMQCDemoEnhanced 页面优化  
**参考文档**: [LLM_Demo_Test_Record_PRD.md](./LLM_Demo_Test_Record_PRD.md)

---

## 📊 执行摘要

### 当前状态
- ✅ **已完成**: 核心流程、布局优化、组件集成
- 🚧 **进行中**: 数据适配与类型修正
- 📋 **待开始**: 体验优化、首次访问引导

### 优化优先级
1. **P0 (必须完成)**: 首次访问体验、快速开始流程、状态持久化
2. **P1 (重要)**: 重置功能、空态提示、引导提示
3. **P2 (优化)**: 性能优化、动画效果、埋点

---

## 🔍 PRD 需求 vs 现有实现对比分析

### ✅ 已实现的功能

| PRD 需求 | 实现状态 | 代码位置 | 备注 |
|---------|---------|---------|------|
| **病历信息卡片** | ✅ 完成 | `MedicalRecordInfoCard.vue` | 9项关键字段展示 |
| **预置示例数据** | ✅ 完成 | `qcDemo.ts:60-185` | 首次病程记录示例 |
| **预置示例加载** | ✅ 完成 | `qcDemo.ts:2106-2146` | `loadPresetExample()` |
| **数据适配层** | ✅ 完成 | `qcDemo.ts:2163-2199` | `currentRecordInfo`, `currentDocumentInfo` |
| **结果总览组件** | ✅ 完成 | `QCResultSummary.vue` | 已集成 |
| **违规列表组件** | ✅ 完成 | `ViolationsList.vue` | 已集成 |
| **折叠区** | ✅ 完成 | `LLMQCDemoEnhanced.vue:396-429` | 统计/日志/性能默认收起 |
| **状态持久化** | ✅ 完成 | `qcDemo.ts:1811-1900` | localStorage 保存/恢复 |

### ⚠️ 部分实现的功能

| PRD 需求 | 当前状态 | 问题描述 | 优化方案 |
|---------|---------|---------|---------|
| **首次访问体验** | ⚠️ 部分 | 缺少首次访问检测和引导提示 | 添加 `llm_qc_demo_first_visit` 标记 |
| **快速开始按钮** | ⚠️ 部分 | 按钮存在但缺少自动跳转逻辑 | 完善 `handleQuickStart()` |
| **手动选择流程** | ⚠️ 部分 | 选择器存在但缺少确认后的跳转 | 优化 `onTargetPicked()` |
| **重置并快速开始** | ⚠️ 部分 | 按钮存在但逻辑不完整 | 添加清理状态逻辑 |
| **空态提示** | ❌ 缺失 | 无结果时缺少友好提示 | 添加空态组件 |
| **引导提示** | ❌ 缺失 | 首次访问无引导文案 | 添加 `a-alert` 引导 |

### ❌ 未实现的功能

| PRD 需求 | 优先级 | 实施难度 | 预计工时 |
|---------|--------|---------|---------|
| **首次访问清理旧状态** | P0 | 低 | 0.5h |
| **快速开始自动跳转** | P0 | 低 | 0.5h |
| **成功提示文案** | P1 | 低 | 0.5h |
| **空态提示组件** | P1 | 中 | 1h |
| **首次访问引导动画** | P2 | 高 | 2h |
| **操作埋点** | P2 | 中 | 1h |

---

## 🎯 核心问题识别

### 问题 1: 首次访问体验不完整 (P0)

**PRD 要求**:
```typescript
onMounted(async () => {
  const FIRST_VISIT_KEY = 'llm_qc_demo_layout_v2_seen'
  
  if (!localStorage.getItem(FIRST_VISIT_KEY)) {
    // 清理旧状态
    await demoStore.clearSavedState?.()
    await demoStore.resetDemoState?.()
    
    // 标记已访问
    localStorage.setItem(FIRST_VISIT_KEY, '1')
    
    // 回到步骤1
    await demoStore.jumpToStep?.('target')
    
    // 显示引导提示
    message.info('欢迎使用：点击"快速开始"或"手动选择"开始体验', 4)
  }
})
```

**当前实现**: ❌ 缺失

**影响**: 用户首次访问时可能看到旧状态，体验混乱

---

### 问题 2: 快速开始流程不完整 (P0)

**PRD 要求**:
1. 点击"快速开始" → 加载预置示例
2. 显示病历卡片
3. **自动跳转到规则配置步骤**

**当前实现**:
```typescript
// LLMQCDemoEnhanced.vue:323
const handleQuickStart = async (reset = false) => {
  try {
    if (reset) {
      await demoStore.resetDemoState()
    }
    
    // 加载预置示例
    demoStore.loadPresetExample('firstCourseRecord')
    
    message.success('已加载预置示例：首次病程记录 - 李明（急性冠脉综合征）')
    
    // ❌ 缺少自动跳转逻辑
  } catch (error) {
    message.error('加载预置示例失败')
  }
}
```

**问题**: `loadPresetExample()` 内部有跳转逻辑，但条件判断可能不触发

---

### 问题 3: 空态提示缺失 (P1)

**PRD 要求**:
```
无结果时显示："尚未产出结果，点击'开始分析'或返回前一步补充条件"
```

**当前实现**: ❌ 缺失

**影响**: 用户在"运行与结果"步骤看到空白页面，不知道下一步操作

---

### 问题 4: 类型断言过多 (P1)

**当前代码**:
```typescript
// LLMQCDemoEnhanced.vue:377-378
<QCResultSummary :result="(demoStore.analysisResult as any)" />
<ViolationsList :violations="(demoStore.analysisResult?.violations || []) as any" />
```

**问题**: 使用 `as any` 绕过类型检查，降低代码质量

---

## 🛠️ 优化实施方案

### Phase 1: P0 核心功能修复 (预计 2h)

#### 1.1 首次访问体验 ✅

**文件**: `LLMQCDemoEnhanced.vue`

**修改点**:
```typescript
// 在 onMounted 中添加
onMounted(async () => {
  const FIRST_VISIT_KEY = 'llm_qc_demo_layout_v2_seen'
  const urlParams = new URLSearchParams(window.location.search)
  const forceClear = urlParams.get('clear') === 'true'
  
  if (!localStorage.getItem(FIRST_VISIT_KEY) || forceClear) {
    // 清理旧状态
    await demoStore.clearSavedState()
    await demoStore.resetDemoState()
    
    // 标记已访问
    if (!forceClear) {
      localStorage.setItem(FIRST_VISIT_KEY, '1')
    }
    
    // 回到步骤1
    demoStore.currentStep = 'target'
    
    // 显示引导提示
    message.info('欢迎使用：点击"快速开始"或"手动选择"开始体验', 4)
  } else {
    // 恢复上次状态
    await demoStore.restoreDemoState()
  }
  
  // 初始化数据
  await demoStore.loadTestData()
})
```

#### 1.2 快速开始自动跳转 ✅

**文件**: `LLMQCDemoEnhanced.vue`

**修改点**:
```typescript
const handleQuickStart = async (reset = false) => {
  try {
    if (reset) {
      await demoStore.resetDemoState()
    }
    
    // 加载预置示例
    demoStore.loadPresetExample('firstCourseRecord')
    
    message.success('✅ 已加载预置示例：首次病程记录 - 李明（急性冠脉综合征）', 3)
    
    // 确保自动跳转到规则配置
    setTimeout(() => {
      if (demoStore.currentStep === 'target') {
        demoStore.currentStep = 'rules'
      }
    }, 300)
  } catch (error) {
    message.error('加载预置示例失败')
  }
}
```

#### 1.3 手动选择后跳转 ✅

**文件**: `LLMQCDemoEnhanced.vue`

**修改点**:
```typescript
const onTargetPicked = (data: any) => {
  if (data.record) {
    demoStore.selectTestRecord(data.record)
  }
  if (data.documents) {
    demoStore.setSelectedDocument(data.documents)
  }
  if (data.rules) {
    demoStore.selectedRules = data.rules
  }
  
  showTargetPicker.value = false
  
  // 自动跳转到规则配置（如果已选择病历和文书）
  if (data.record && data.documents && data.documents.length > 0) {
    message.success('已选择病历与文书，请配置质控规则')
    setTimeout(() => {
      demoStore.currentStep = 'rules'
    }, 300)
  }
}
```

---

### Phase 2: P1 体验优化 (预计 2h)

#### 2.1 空态提示组件 ✅

**新建文件**: `src/components/demo/EmptyResultState.vue`

```vue
<template>
  <a-empty
    :image="Empty.PRESENTED_IMAGE_SIMPLE"
    description="尚未产出质控结果"
  >
    <template #description>
      <p class="text-gray-600">
        尚未产出结果，点击"开始分析"或返回前一步补充条件
      </p>
    </template>
    <a-space>
      <a-button type="primary" @click="$emit('start-analysis')">
        <PlayCircleOutlined />
        开始分析
      </a-button>
      <a-button @click="$emit('go-back')">
        <LeftOutlined />
        返回上一步
      </a-button>
    </a-space>
  </a-empty>
</template>

<script setup lang="ts">
import { Empty } from 'ant-design-vue'
import { PlayCircleOutlined, LeftOutlined } from '@ant-design/icons-vue'

defineEmits(['start-analysis', 'go-back'])
</script>
```

#### 2.2 集成空态提示 ✅

**文件**: `LLMQCDemoEnhanced.vue`

**修改点**:
```vue
<!-- 运行与结果 -->
<div v-else class="step-content">
  <!-- 有结果：显示总结 + 违规列表 -->
  <template v-if="demoStore.analysisResult">
    <QCResultSummary :result="demoStore.analysisResult" />
    <ViolationsList class="mt-4" :violations="demoStore.analysisResult.violations || []" />
  </template>
  
  <!-- 无结果：显示空态提示 -->
  <EmptyResultState
    v-else-if="!demoStore.isRunning"
    @start-analysis="handleStartDemo"
    @go-back="demoStore.currentStep = 'rules'"
  />
  
  <!-- 分析中：显示分析面板 -->
  <QCAnalysisDemoPanel
    v-if="demoStore.isRunning || demoStore.analysisResult"
    :analysis-steps="demoStore.analysisSteps"
    :analysis-result="demoStore.analysisResult"
    :is-running="demoStore.isRunning"
    @analysis-complete="handleAnalysisComplete"
  />
</div>
```

#### 2.3 移除类型断言 ✅

**文件**: `LLMQCDemoEnhanced.vue`

**修改点**:
```typescript
// 修改前
<QCResultSummary :result="(demoStore.analysisResult as any)" />
<ViolationsList :violations="(demoStore.analysisResult?.violations || []) as any" />

// 修改后
<QCResultSummary :result="demoStore.analysisResult!" />
<ViolationsList :violations="demoStore.analysisResult?.violations || []" />
```

---

### Phase 3: P2 高级优化 (预计 3h)

#### 3.1 首次访问引导动画

**实施方案**: 使用 `driver.js` 或自定义 Tour 组件

#### 3.2 操作埋点

**实施方案**: 集成 Google Analytics 或自定义埋点

#### 3.3 性能优化

**实施方案**:
- 懒加载组件
- 虚拟滚动
- 防抖/节流

---

## ✅ 验收清单

### P0 功能验收

- [ ] 首次访问自动清理旧状态
- [ ] 首次访问显示引导提示
- [ ] 快速开始加载预置示例并自动跳转
- [ ] 手动选择后自动跳转到规则配置
- [ ] 病历信息卡片正确显示9项字段
- [ ] 状态持久化正常工作
- [ ] 刷新页面恢复上次状态

### P1 功能验收

- [ ] 重置并快速开始功能正常
- [ ] 无结果时显示空态提示
- [ ] 空态提示可点击"开始分析"
- [ ] 空态提示可点击"返回上一步"
- [ ] 移除所有 `as any` 类型断言
- [ ] TypeScript 编译无错误

### P2 功能验收

- [ ] 首次访问引导动画流畅
- [ ] 关键操作已埋点
- [ ] 首屏渲染时间 ≤ 1s
- [ ] 预置示例加载 ≤ 500ms

---

## 📅 实施时间表

| 阶段 | 任务 | 预计工时 | 负责人 | 状态 |
|------|------|---------|--------|------|
| Phase 1 | 首次访问体验 | 0.5h | - | 📋 待开始 |
| Phase 1 | 快速开始自动跳转 | 0.5h | - | 📋 待开始 |
| Phase 1 | 手动选择后跳转 | 0.5h | - | 📋 待开始 |
| Phase 1 | 状态持久化测试 | 0.5h | - | 📋 待开始 |
| Phase 2 | 空态提示组件 | 1h | - | 📋 待开始 |
| Phase 2 | 移除类型断言 | 0.5h | - | 📋 待开始 |
| Phase 2 | 成功提示文案 | 0.5h | - | 📋 待开始 |
| Phase 3 | 引导动画 | 2h | - | 📋 待开始 |
| Phase 3 | 操作埋点 | 1h | - | 📋 待开始 |

**总计**: 约 7 小时

---

## 📝 附录

### A. 关键代码位置

| 功能 | 文件路径 | 行号 |
|------|---------|------|
| 主页面 | `src/views/demo/LLMQCDemoEnhanced.vue` | 1-1312 |
| Store | `src/stores/qcDemo.ts` | 1-2340 |
| 病历卡片 | `src/components/demo/MedicalRecordInfoCard.vue` | 1-125 |
| 选择器 | `src/components/demo/RecordDocumentPicker.vue` | 1-684 |
| 预置示例 | `src/stores/qcDemo.ts` | 60-185 |
| 加载方法 | `src/stores/qcDemo.ts` | 2106-2146 |
| 数据适配 | `src/stores/qcDemo.ts` | 2163-2199 |

### B. 测试用例

见 PRD 文档第 6 节验收标准。

---

**文档维护者**: MedQC 开发团队  
**最后更新**: 2025-10-15  
**下次审查**: 实施完成后

