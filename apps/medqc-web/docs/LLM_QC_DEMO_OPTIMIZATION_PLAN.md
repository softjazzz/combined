# LLM质控演示增强版优化实施计划

**计划时间**: 2025-10-14  
**目标**: 优化 `LLMQCDemoEnhanced.vue`，借鉴 `SichuanQCDemo.vue` 的优点  
**预计工作量**: 26-35 小时（约 3-4 个工作日）

---

## 📋 任务清单总览

| 任务 | 优先级 | 工作量 | 状态 |
|------|--------|--------|------|
| 1. 添加预置示例快速加载功能 | 🔴 P0 | 4-6h | [ ] |
| 2. 添加病历信息卡片组件 | 🟡 P1 | 3-4h | [ ] |
| 3. 集成 QCResultSummary 组件 | 🟡 P1 | 3-4h | [ ] |
| 4. 集成 ViolationsList 组件 | 🟡 P1 | 3-4h | [ ] |
| 5. 添加使用说明入口 | 🟡 P1 | 4-5h | [ ] |
| 6. 增强性能指标展示 | 🟢 P2 | 3-4h | [ ] |
| 7. 添加 Markdown 导出功能 | 🟢 P2 | 4-5h | [ ] |
| 8. 使用 PageHeader 组件 | 🟢 P2 | 2-3h | [ ] |

---

## 🔴 P0 阶段：核心功能增强

### 任务 1: 添加预置示例快速加载功能

**目标**: 提供一键加载预置示例的功能，提升演示效率

#### 1.1 实施步骤

**步骤 1**: 在 `qcDemo.ts` Store 中添加预置示例数据

```typescript
// 文件: src/stores/qcDemo.ts

// 预置示例数据
const PRESET_EXAMPLES = {
  firstCourseRecord: {
    id: 'preset-first-course-record',
    title: '首次病程记录 - 李明（急性冠脉综合征）',
    type: '首次病程记录',
    content: `首次病程记录
记录时间：2025年10月11日 15:00

一、患者基本信息
姓名：李明
性别：男
年龄：58岁
科室：心内科
住院号：2025001234
床号：15床
入院时间：2025年10月11日 09:30

二、主诉
反复胸闷、胸痛3天，加重伴气促1天。

三、现病史
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后...
（完整内容参考 sichuanQC.ts）`,
    patientInfo: {
      patientName: '李明',
      age: 58,
      gender: '男',
      department: '心内科',
      admissionNumber: '2025001234',
      bedNumber: '15床',
      admissionTime: '2025年10月11日 09:30',
      recordTime: '2025年10月11日 15:00',
      diagnosis: '急性冠脉综合征（ACS）'
    }
  },
  admissionRecord: {
    id: 'preset-admission-record',
    title: '入院记录 - 张华（肺炎）',
    type: '入院记录',
    content: `入院记录...`,
    patientInfo: { /* ... */ }
  },
  dischargeRecord: {
    id: 'preset-discharge-record',
    title: '出院记录 - 王芳（阑尾炎术后）',
    type: '出院记录',
    content: `出院记录...`,
    patientInfo: { /* ... */ }
  }
}

// 添加状态
const presetExamples = ref(PRESET_EXAMPLES)
const currentPresetExample = ref<string | null>(null)

// 添加方法
const loadPresetExample = (exampleKey: string) => {
  const example = PRESET_EXAMPLES[exampleKey]
  if (!example) {
    message.error('预置示例不存在')
    return
  }
  
  // 设置病历内容
  testRecord.value = {
    id: example.id,
    patient_name: example.patientInfo.patientName,
    admission_number: example.patientInfo.admissionNumber,
    department: example.patientInfo.department,
    // ... 其他字段
  }
  
  // 设置文书内容
  selectedDocument.value = {
    id: example.id,
    title: example.title,
    type: example.type,
    content: example.content
  }
  
  currentPresetExample.value = exampleKey
  
  addDemoLog('info', `已加载预置示例：${example.title}`)
  message.success(`已加载预置示例：${example.title}`)
  
  // 自动跳转到规则配置步骤
  if (currentStep.value === 'target') {
    nextStep()
  }
}
```

**步骤 2**: 修改 `RecordDocumentPicker.vue` 组件，添加预置示例选项卡

```vue
<!-- 文件: src/components/demo/RecordDocumentPicker.vue -->

<template>
  <a-modal
    v-model:open="visible"
    title="选择病历与文书"
    width="900px"
    :footer="null"
  >
    <a-tabs v-model:activeKey="activeTab">
      <!-- 新增：预置示例选项卡 -->
      <a-tab-pane key="preset" tab="预置示例">
        <a-alert
          message="快速加载预置示例"
          description="选择预置示例可快速体验质控流程，无需手动输入病历内容"
          type="info"
          show-icon
          class="mb-4"
        />
        
        <a-list
          :data-source="presetExamplesList"
          :grid="{ gutter: 16, column: 1 }"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-card hoverable @click="handleSelectPreset(item.key)">
                <a-card-meta
                  :title="item.title"
                  :description="item.description"
                >
                  <template #avatar>
                    <a-avatar :style="{ backgroundColor: item.color }">
                      <FileTextOutlined />
                    </a-avatar>
                  </template>
                </a-card-meta>
                
                <template #actions>
                  <a-button type="primary" @click.stop="handleSelectPreset(item.key)">
                    <ThunderboltOutlined />
                    加载此示例
                  </a-button>
                </template>
              </a-card>
            </a-list-item>
          </template>
        </a-list>
      </a-tab-pane>
      
      <!-- 原有：病历列表选项卡 -->
      <a-tab-pane key="records" tab="病历列表">
        <!-- 原有内容 -->
      </a-tab-pane>
    </a-tabs>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useQCDemoStore } from '@/stores/qcDemo'

const demoStore = useQCDemoStore()
const activeTab = ref('preset') // 默认显示预置示例

const presetExamplesList = [
  {
    key: 'firstCourseRecord',
    title: '首次病程记录 - 李明（急性冠脉综合征）',
    description: '58岁男性，急性冠脉综合征（ACS），包含完整的病历结构和质控缺陷示例',
    color: '#1890ff'
  },
  {
    key: 'admissionRecord',
    title: '入院记录 - 张华（肺炎）',
    description: '45岁女性，社区获得性肺炎，标准入院记录格式',
    color: '#52c41a'
  },
  {
    key: 'dischargeRecord',
    title: '出院记录 - 王芳（阑尾炎术后）',
    description: '32岁女性，急性阑尾炎术后，完整出院记录',
    color: '#faad14'
  }
]

const handleSelectPreset = (key: string) => {
  demoStore.loadPresetExample(key)
  emit('picked')
  visible.value = false
}
</script>
```

**步骤 3**: 在 `LLMQCDemoEnhanced.vue` 中添加快捷加载按钮

```vue
<!-- 文件: src/views/demo/LLMQCDemoEnhanced.vue -->

<!-- 在步骤1（target）中添加快捷按钮 -->
<div v-if="demoStore.currentStep === 'target'">
  <a-alert
    message="快速开始"
    description="点击下方按钮快速加载预置示例，或手动选择病历与文书"
    type="info"
    show-icon
    class="mb-4"
  />
  
  <a-space direction="vertical" style="width: 100%">
    <a-button
      type="primary"
      size="large"
      block
      @click="handleQuickStart"
    >
      <ThunderboltOutlined />
      快速开始（加载预置示例）
    </a-button>
    
    <a-button
      size="large"
      block
      @click="showTargetPicker = true"
    >
      <FileSearchOutlined />
      手动选择病历与文书
    </a-button>
  </a-space>
</div>

<script setup lang="ts">
const handleQuickStart = () => {
  demoStore.loadPresetExample('firstCourseRecord')
}
</script>
```

#### 1.2 验收标准

- [ ] 预置示例数据已添加到 Store
- [ ] RecordDocumentPicker 组件新增"预置示例"选项卡
- [ ] 点击"加载此示例"按钮可成功加载预置示例
- [ ] 加载后自动跳转到规则配置步骤
- [ ] 显示成功提示消息
- [ ] 日志面板记录加载操作

#### 1.3 测试用例

1. **测试用例 1**: 加载首次病程记录示例
   - 操作：点击"快速开始"按钮
   - 预期：加载李明的首次病程记录，跳转到规则配置步骤

2. **测试用例 2**: 从预置示例列表选择
   - 操作：打开 RecordDocumentPicker，切换到"预置示例"选项卡，选择入院记录
   - 预期：加载张华的入院记录，关闭模态框

3. **测试用例 3**: 预置示例与手动选择切换
   - 操作：先加载预置示例，再手动选择其他病历
   - 预期：手动选择的病历覆盖预置示例

---

## 🟡 P1 阶段：用户体验提升

### 任务 2: 添加病历信息卡片组件

**目标**: 选择病历后，展示病历关键信息

#### 2.1 实施步骤

**步骤 1**: 创建 `MedicalRecordInfoCard.vue` 组件

```vue
<!-- 文件: src/components/demo/MedicalRecordInfoCard.vue -->

<template>
  <a-card title="病历信息" :bordered="false" class="medical-record-info-card">
    <a-descriptions :column="2" bordered size="small">
      <a-descriptions-item label="患者姓名">
        {{ recordInfo.patientName || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="年龄/性别">
        {{ recordInfo.age || '-' }}岁/{{ recordInfo.gender || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="科室">
        {{ recordInfo.department || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="住院号">
        {{ recordInfo.admissionNumber || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="床号">
        {{ recordInfo.bedNumber || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="入院时间">
        {{ recordInfo.admissionTime || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="记录时间">
        {{ recordInfo.recordTime || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="初步诊断" :span="2">
        {{ recordInfo.diagnosis || '-' }}
      </a-descriptions-item>
    </a-descriptions>
    
    <!-- 文书信息 -->
    <a-divider />
    <h4>已选文书</h4>
    <a-tag v-if="documentInfo" color="blue">
      {{ documentInfo.type || documentInfo.title }}
    </a-tag>
    <a-tag v-else color="default">未选择文书</a-tag>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  recordInfo: {
    patientName?: string
    age?: number
    gender?: string
    department?: string
    admissionNumber?: string
    bedNumber?: string
    admissionTime?: string
    recordTime?: string
    diagnosis?: string
  }
  documentInfo?: {
    type?: string
    title?: string
  }
}

const props = defineProps<Props>()
</script>
```

**步骤 2**: 在 `qcDemo.ts` Store 中添加病历信息解析

```typescript
// 文件: src/stores/qcDemo.ts

// 添加计算属性
const currentRecordInfo = computed(() => {
  if (!testRecord.value) return {}
  
  return {
    patientName: testRecord.value.patient_name,
    age: testRecord.value.age,
    gender: testRecord.value.gender,
    department: testRecord.value.department,
    admissionNumber: testRecord.value.admission_number,
    bedNumber: testRecord.value.bed_number,
    admissionTime: testRecord.value.admission_time,
    recordTime: testRecord.value.record_time,
    diagnosis: testRecord.value.diagnosis
  }
})

const currentDocumentInfo = computed(() => {
  if (!selectedDocument.value) return null
  
  return {
    type: selectedDocument.value.type,
    title: selectedDocument.value.title
  }
})
```

**步骤 3**: 在 `LLMQCDemoEnhanced.vue` 中集成组件

```vue
<!-- 文件: src/views/demo/LLMQCDemoEnhanced.vue -->

<template>
  <!-- 在步骤1（target）中显示病历信息卡片 -->
  <div v-if="demoStore.currentStep === 'target'">
    <!-- 已选病历信息 -->
    <MedicalRecordInfoCard
      v-if="demoStore.testRecord"
      :record-info="demoStore.currentRecordInfo"
      :document-info="demoStore.currentDocumentInfo"
      class="mb-4"
    />
    
    <!-- 选择按钮 -->
    <a-button @click="showTargetPicker = true">
      选择病历与文书
    </a-button>
  </div>
</template>

<script setup lang="ts">
import MedicalRecordInfoCard from '@/components/demo/MedicalRecordInfoCard.vue'
</script>
```

#### 2.2 验收标准

- [ ] MedicalRecordInfoCard 组件已创建
- [ ] 选择病历后自动显示信息卡片
- [ ] 信息卡片正确显示所有字段
- [ ] 未选择病历时不显示卡片
- [ ] 响应式布局正常

---

### 任务 3: 集成 QCResultSummary 组件

**目标**: 使用专用组件展示质控结果总结

#### 3.1 实施步骤

**步骤 1**: 调整 QCResultSummary 组件以适配 LLMQCDemoEnhanced 的数据结构

```typescript
// 检查数据结构差异
// SichuanQCDemo: qcResult.evaluation_summary
// LLMQCDemoEnhanced: analysisResult

// 可能需要添加数据转换逻辑
```

**步骤 2**: 在 LLMQCDemoEnhanced 中导入并使用组件

```vue
<!-- 文件: src/views/demo/LLMQCDemoEnhanced.vue -->

<template>
  <!-- 在步骤3（run）中显示结果总结 -->
  <div v-if="demoStore.currentStep === 'run' && demoStore.analysisResult">
    <QCResultSummary :result="demoStore.analysisResult" />
  </div>
</template>

<script setup lang="ts">
import QCResultSummary from '@/components/demo/QCResultSummary.vue'
</script>
```

#### 3.2 验收标准

- [ ] QCResultSummary 组件成功集成
- [ ] 数据正确显示（等级、合规率、违规数）
- [ ] 进度条和统计卡片正常工作
- [ ] 样式与整体页面协调

---

### 任务 4: 集成 ViolationsList 组件

**目标**: 使用专用组件展示违规项列表

#### 4.1 实施步骤

**步骤 1**: 调整 ViolationsList 组件以适配数据结构

**步骤 2**: 在 LLMQCDemoEnhanced 中导入并使用组件

```vue
<template>
  <div v-if="demoStore.currentStep === 'run' && demoStore.analysisResult">
    <QCResultSummary :result="demoStore.analysisResult" />
    <ViolationsList :violations="demoStore.violations" class="mt-4" />
  </div>
</template>

<script setup lang="ts">
import ViolationsList from '@/components/demo/ViolationsList.vue'
</script>
```

#### 4.2 验收标准

- [ ] ViolationsList 组件成功集成
- [ ] 违规项列表正确显示
- [ ] 折叠面板交互正常
- [ ] 严重程度统计正确

---

### 任务 5: 添加使用说明入口

**目标**: 提供使用说明，降低学习成本

#### 5.1 实施步骤

**步骤 1**: 创建使用说明模态框组件

```vue
<!-- 文件: src/components/demo/UserGuideModal.vue -->

<template>
  <a-modal
    v-model:open="visible"
    title="使用说明"
    width="800px"
    :footer="null"
  >
    <a-tabs>
      <a-tab-pane key="quick-start" tab="快速开始">
        <h3>1. 选择病历与文书</h3>
        <p>点击"快速开始"按钮加载预置示例，或手动选择病历与文书。</p>
        
        <h3>2. 配置质控规则</h3>
        <p>选择需要应用的质控规则，可按分类筛选或搜索。</p>
        
        <h3>3. 运行质控分析</h3>
        <p>点击"开始分析"按钮，系统将调用 LLM API 进行质控分析。</p>
        
        <h3>4. 查看结果</h3>
        <p>分析完成后，查看质控结果、违规项和改进建议。</p>
      </a-tab-pane>
      
      <a-tab-pane key="features" tab="功能说明">
        <!-- 功能说明 -->
      </a-tab-pane>
      
      <a-tab-pane key="shortcuts" tab="快捷键">
        <!-- 快捷键说明 -->
      </a-tab-pane>
    </a-tabs>
  </a-modal>
</template>
```

**步骤 2**: 在页面头部添加"使用说明"按钮

```vue
<!-- 文件: src/views/demo/LLMQCDemoEnhanced.vue -->

<template>
  <div class="demo-header">
    <div class="header-content">
      <div class="title-section">
        <h1>LLM集成质控系统演示</h1>
        <a-button type="link" @click="showUserGuide = true">
          <QuestionCircleOutlined />
          使用说明
        </a-button>
      </div>
    </div>
  </div>
  
  <UserGuideModal v-model:visible="showUserGuide" />
</template>
```

#### 5.2 验收标准

- [ ] 使用说明模态框已创建
- [ ] 点击"使用说明"按钮可打开模态框
- [ ] 使用说明内容完整、清晰
- [ ] 支持快捷键提示

---

## 🟢 P2 阶段：锦上添花

### 任务 6-8: 增强性能指标展示、Markdown 导出、PageHeader 组件

（详细步骤省略，参考 P0 和 P1 的格式）

---

## 📊 进度跟踪

### 第 1 天（P0 阶段）
- [ ] 任务 1: 添加预置示例快速加载功能（4-6h）

### 第 2 天（P1 阶段）
- [ ] 任务 2: 添加病历信息卡片组件（3-4h）
- [ ] 任务 3: 集成 QCResultSummary 组件（3-4h）

### 第 3 天（P1 阶段）
- [ ] 任务 4: 集成 ViolationsList 组件（3-4h）
- [ ] 任务 5: 添加使用说明入口（4-5h）

### 第 4 天（P2 阶段，可选）
- [ ] 任务 6: 增强性能指标展示（3-4h）
- [ ] 任务 7: 添加 Markdown 导出功能（4-5h）
- [ ] 任务 8: 使用 PageHeader 组件（2-3h）

---

## ✅ 成功标准

1. **功能完整性**: 所有 P0 和 P1 任务完成
2. **用户体验**: 演示流程流畅，操作简单
3. **代码质量**: 无语法错误，通过 ESLint 检查
4. **测试通过**: 所有测试用例通过
5. **文档完善**: 使用说明清晰完整

---

**计划生成时间**: 2025-10-14  
**计划人**: AI Assistant  
**审核状态**: ✅ 待用户确认

