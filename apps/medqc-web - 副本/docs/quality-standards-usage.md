# 质控标准JSON数据使用指南

## 📋 概述

本文档介绍如何使用转换后的质控标准JSON数据，包括数据结构、API使用和实际应用示例。

## 🗂️ 数据结构

### 文件位置
- **JSON数据**: `src/data/quality-standards.json`
- **TypeScript类型**: `src/types/quality-standards.ts`
- **加载器工具**: `src/utils/quality-standards-loader.ts`

### 数据统计
- **评分项目组**: 6个
- **评分项目**: 6个
- **评分内容**: 234个
- **文件大小**: ~1.5MB

## 📊 数据结构说明

```typescript
interface QualityStandards {
  metadata: {
    title: string;           // "住院质量评定标准"
    version: string;         // "2024-04-03"
    totalGroups: number;     // 6
    totalItems: number;      // 6
    totalContents: number;   // 234
    generatedAt: string;     // ISO时间戳
  };
  groups: QualityStandardGroup[];
}

interface QualityStandardGroup {
  name: string;              // 评分项目组名称，如"入院记录"
  totalScore: number;        // 项目组总分值
  items: QualityStandardItem[];
}

interface QualityStandardItem {
  name: string;              // 评分项目名称
  totalScore: number;        // 项目总分值
  contents: QualityStandardContent[];
}

interface QualityStandardContent {
  content: string;           // 评分内容
  rule: string;              // 评分规则，如"单否丙"
  deductionScore: number;    // 扣分分值
  qualityPointId: string;    // 质控点ID
  qualityPointName: string;  // 质控点名称
  document: string;          // 质控文书
  departments: string[];     // 生效科室列表
  alertLevel: string;        // 提醒等级
  isEnabled: boolean;        // 是否启用
  isEffectiveToDoctor: boolean; // 是否生效到医生端
}
```

## 🚀 使用方法

### 1. 基础使用

```typescript
import { loadQualityStandards, getAllGroups, getStatistics } from '@/utils/quality-standards-loader';

// 加载完整数据
const qualityStandards = await loadQualityStandards();
console.log(qualityStandards.metadata);

// 获取所有项目组
const groups = await getAllGroups();
console.log(`共有${groups.length}个评分项目组`);

// 获取统计信息
const stats = await getStatistics();
console.log(stats);
```

### 2. 查询特定数据

```typescript
import { 
  getGroupByName, 
  getItemByName, 
  getContentByQualityPointId,
  getContentsByDepartment 
} from '@/utils/quality-standards-loader';

// 获取特定项目组
const admissionGroup = await getGroupByName('入院记录');
if (admissionGroup) {
  console.log(`${admissionGroup.name}: ${admissionGroup.totalScore}分`);
}

// 获取特定项目
const admissionItem = await getItemByName('入院记录');
if (admissionItem) {
  console.log(`${admissionItem.name}包含${admissionItem.contents.length}个评分内容`);
}

// 根据质控点ID获取内容
const content = await getContentByQualityPointId('09791');
if (content) {
  console.log(`质控点: ${content.qualityPointName}`);
}

// 获取特定科室的质控内容
const deptContents = await getContentsByDepartment('外三科');
console.log(`外三科相关质控内容: ${deptContents.length}个`);
```

### 3. 搜索和过滤

```typescript
import { 
  searchContents, 
  getContentsByAlertLevel,
  getEnabledContents,
  getDoctorEffectiveContents 
} from '@/utils/quality-standards-loader';

// 搜索质控内容
const searchResults = await searchContents('入院记录');
console.log(`搜索结果: ${searchResults.length}个`);

// 按提醒等级过滤
const highAlertContents = await getContentsByAlertLevel('高');
console.log(`高级别提醒: ${highAlertContents.length}个`);

// 获取启用的内容
const enabledContents = await getEnabledContents();
console.log(`启用的质控内容: ${enabledContents.length}个`);

// 获取生效到医生端的内容
const doctorContents = await getDoctorEffectiveContents();
console.log(`医生端生效: ${doctorContents.length}个`);
```

### 4. 缓存管理

```typescript
import { QualityStandardsCache } from '@/utils/quality-standards-loader';

// 预加载数据
await QualityStandardsCache.preload();

// 检查缓存状态
if (QualityStandardsCache.isCached()) {
  console.log('数据已缓存');
}

// 清除缓存
QualityStandardsCache.clear();
```

## 💡 实际应用示例

### 1. 质控规则验证

```typescript
import { getAllContents } from '@/utils/quality-standards-loader';

async function validateMedicalRecord(recordData: any) {
  const contents = await getAllContents();
  const results = [];
  
  for (const content of contents) {
    if (content.isEnabled) {
      // 根据质控规则验证病历
      const isValid = validateRule(recordData, content.rule);
      if (!isValid) {
        results.push({
          qualityPointId: content.qualityPointId,
          qualityPointName: content.qualityPointName,
          content: content.content,
          deductionScore: content.deductionScore,
          alertLevel: content.alertLevel
        });
      }
    }
  }
  
  return results;
}
```

### 2. 科室质控配置

```typescript
import { getContentsByDepartment } from '@/utils/quality-standards-loader';

async function getDepartmentQualityConfig(department: string) {
  const contents = await getContentsByDepartment(department);
  
  return {
    department,
    totalRules: contents.length,
    enabledRules: contents.filter(c => c.isEnabled).length,
    doctorEffectiveRules: contents.filter(c => c.isEffectiveToDoctor).length,
    alertLevels: [...new Set(contents.map(c => c.alertLevel))],
    totalDeductionScore: contents.reduce((sum, c) => sum + c.deductionScore, 0)
  };
}
```

### 3. 动态表单生成

```typescript
import { getAllGroups } from '@/utils/quality-standards-loader';

async function generateQualityControlForm() {
  const groups = await getAllGroups();
  
  return groups.map(group => ({
    groupName: group.name,
    totalScore: group.totalScore,
    items: group.items.map(item => ({
      itemName: item.name,
      totalScore: item.totalScore,
      fields: item.contents.map(content => ({
        id: content.qualityPointId,
        label: content.qualityPointName,
        description: content.content,
        rule: content.rule,
        maxDeduction: content.deductionScore,
        required: content.isEnabled,
        alertLevel: content.alertLevel
      }))
    }))
  }));
}
```

## 🔧 集成到现有系统

### 1. 更新质控分析服务

```typescript
// 在 src/lib/qc-analysis-simple.ts 中集成
import { getAllContents } from '@/utils/quality-standards-loader';

export class SimpleQCAnalysisService {
  private async loadQualityRules() {
    const contents = await getAllContents();
    return contents.filter(c => c.isEnabled);
  }
  
  async analyzeRecord(request: SimpleQCRequest): Promise<SimpleQCResult> {
    const rules = await this.loadQualityRules();
    // 使用加载的规则进行分析...
  }
}
```

### 2. 更新UI组件

```vue
<!-- 在Vue组件中使用 -->
<template>
  <div class="quality-standards">
    <div v-for="group in groups" :key="group.name" class="group">
      <h3>{{ group.name }} ({{ group.totalScore }}分)</h3>
      <div v-for="item in group.items" :key="item.name" class="item">
        <h4>{{ item.name }}</h4>
        <div v-for="content in item.contents" :key="content.qualityPointId" class="content">
          <span class="badge" :class="content.alertLevel">{{ content.alertLevel }}</span>
          <span>{{ content.qualityPointName }}</span>
          <span class="score">-{{ content.deductionScore }}分</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getAllGroups } from '@/utils/quality-standards-loader';

const groups = ref([]);

onMounted(async () => {
  groups.value = await getAllGroups();
});
</script>
```

## 📈 性能优化建议

1. **预加载**: 在应用启动时预加载数据
2. **缓存**: 利用内置缓存机制避免重复加载
3. **按需加载**: 只加载当前需要的数据
4. **索引优化**: 为频繁查询的字段创建索引

## 🛠️ 维护和更新

### 重新生成JSON数据
```bash
# 当CSV文件更新时，重新运行转换脚本
node scripts/csv-to-json-converter.js
```

### 类型定义同步
转换脚本会自动生成最新的TypeScript类型定义，确保类型安全。

## 📝 注意事项

1. **文件大小**: JSON文件较大(~1.5MB)，建议使用懒加载
2. **编码格式**: 确保CSV文件使用UTF-8编码
3. **数据验证**: 在生产环境中添加数据完整性验证
4. **版本控制**: 跟踪质控标准的版本变化

## 🔗 相关文件

- `/scripts/csv-to-json-converter.js` - 转换脚本
- `/src/data/quality-standards.json` - JSON数据文件
- `/src/types/quality-standards.ts` - TypeScript类型定义
- `/src/utils/quality-standards-loader.ts` - 数据加载器
- `/docs/simplified-architecture.md` - 简化架构文档 