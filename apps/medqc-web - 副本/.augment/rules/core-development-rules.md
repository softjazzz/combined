---
title: "医疗质控系统核心开发规则"
description: "Augment AI在医疗病案质控系统项目中的核心开发指导原则"
version: "2.0"
category: "core"
priority: "critical"
type: "manual"
---
# 医疗质控系统核心开发规则

## 🎯 项目概述
- **项目名称**: 医疗病案质控系统
- **技术栈**: Vue 3 + TypeScript + Supabase + DeepSeek AI
- **项目路径**: `/home/ubuntu/icd`
- **包管理器**: pnpm 8.15.0

## 📋 核心开发原则

### 1. 代码质量要求
- **强制使用TypeScript**: 所有新文件必须使用`.ts`或`.vue`扩展名
- **类型安全**: 禁止使用`any`类型，必须提供明确的类型定义
- **组件规范**: Vue组件必须使用Composition API和`<script setup>`语法

```typescript
// ✅ 正确示例
interface MedicalRecord {
  id: string
  patientName: string
  recordType: 'inpatient' | 'outpatient'
  createdAt: Date
}

// ❌ 错误示例
const data: any = {} // 禁止使用any类型
```

### 2. 文件命名规范
- **组件文件**: PascalCase (如: `QualityControlPanel.vue`)
- **工具函数**: kebab-case (如: `medical-record-validator.ts`)
- **类型定义**: kebab-case (如: `quality-control-types.ts`)
- **服务文件**: kebab-case (如: `supabase-service.ts`)

### 3. 代码结构要求
```
src/
├── components/          # 可复用组件
├── views/              # 页面组件
├── services/           # 业务服务层
├── utils/              # 工具函数
├── types/              # 类型定义
├── composables/        # Vue组合式函数
└── config/             # 配置文件
```

### 4. 错误处理规范
- 所有异步操作必须包含错误处理
- 使用统一的错误处理机制
- 提供用户友好的错误提示

```typescript
// ✅ 正确示例
try {
  const result = await medicalRecordService.create(data)
  showSuccess('病历创建成功')
} catch (error) {
  console.error('创建病历失败:', error)
  showError('创建病历失败，请重试')
}
```

## 🔧 开发工具配置
- **IDE**: 推荐使用VSCode
- **必装插件**: Vue Language Features, TypeScript Importer
- **代码格式化**: 使用Prettier配置
- **代码检查**: 使用ESLint配置

## 📝 注释规范
- 所有公共函数必须包含JSDoc注释
- 复杂业务逻辑必须添加中文注释
- 医疗相关代码必须包含业务背景说明

```typescript
/**
 * 验证病历记录的完整性
 * @param record 病历记录对象
 * @param rules 质控规则数组
 * @returns 验证结果，包含错误信息和建议
 */
async function validateMedicalRecord(
  record: MedicalRecord, 
  rules: QCRule[]
): Promise<ValidationResult> {
  // 实现逻辑...
}
```