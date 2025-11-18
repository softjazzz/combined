# 文书内容预览功能实现总结

## 功能概述

在质控演示页面的"选择文书"步骤中，为每个可用文书添加了**内容预览**功能。用户可以在选择文书之前，先预览文书的完整内容，帮助做出更准确的选择。

## 实现方案

### 选择的方案：**Drawer（抽屉）组件**

**理由**：
- ✅ 不会完全遮挡主界面，用户可以看到左侧的病历列表
- ✅ 适合显示长文本内容，提供更大的阅读空间
- ✅ 从右侧滑出，符合用户的阅读习惯
- ✅ 可以在预览的同时直接选择文书，提升操作效率

## 修改的文件

### `health-qc-monorepo/apps/medqc-web/src/components/demo/TargetSelectionStep.vue`

**修改内容**：

#### 1. 模板部分（Template）

**位置**：第 207-254 行

**修改**：在文书列表项的 `actions` 插槽中添加预览按钮

```vue
<template #actions>
  <a-space>
    <a-tooltip title="预览文书内容">
      <a-button
        type="link"
        size="small"
        @click.stop="handlePreviewDocument(item)"
      >
        <EyeOutlined />
      </a-button>
    </a-tooltip>
    <CheckCircleOutlined
      v-if="isDocumentSelected(item)"
      style="color: #52c41a; font-size: 18px"
    />
  </a-space>
</template>
```

**关键点**：
- 使用 `@click.stop` 阻止事件冒泡，避免触发文书选择
- 使用 `EyeOutlined` 图标表示预览功能
- 使用 `a-tooltip` 提供友好的提示

**位置**：第 260-341 行

**新增**：文书内容预览抽屉组件

```vue
<a-drawer
  v-model:open="previewDrawerVisible"
  title="文书内容预览"
  placement="right"
  :width="720"
  :body-style="{ paddingBottom: '80px' }"
>
  <div v-if="previewDocument" class="document-preview">
    <!-- 文书信息 -->
    <a-descriptions :column="1" bordered size="small" class="document-info">
      <a-descriptions-item label="文书标题">
        <a-space>
          <FileTextOutlined />
          <strong>{{ previewDocument.title || previewDocument.type || '未命名文书' }}</strong>
        </a-space>
      </a-descriptions-item>
      <a-descriptions-item label="文书类型">
        {{ previewDocument.document_type || previewDocument.type || '未知类型' }}
      </a-descriptions-item>
      <a-descriptions-item label="创建时间" v-if="previewDocument.created_at">
        <CalendarOutlined /> {{ formatDate(previewDocument.created_at) }}
      </a-descriptions-item>
      <a-descriptions-item label="文档ID" v-if="previewDocument.id">
        <a-typography-text copyable>{{ previewDocument.id }}</a-typography-text>
      </a-descriptions-item>
    </a-descriptions>

    <a-divider />

    <!-- 文书内容 -->
    <div class="document-content-section">
      <h4>
        <FileSearchOutlined />
        文书内容
        <a-tag v-if="getContentLength(previewDocument)" color="blue" style="margin-left: 8px">
          {{ getContentLength(previewDocument) }} 字
        </a-tag>
      </h4>
      
      <div v-if="getDocumentContent(previewDocument)" class="content-wrapper">
        <pre class="content-text">{{ getDocumentContent(previewDocument) }}</pre>
      </div>
      <a-empty v-else description="该文书暂无内容" />
    </div>
  </div>

  <!-- 抽屉底部操作按钮 -->
  <template #footer>
    <a-space>
      <a-button @click="previewDrawerVisible = false">关闭</a-button>
      <a-button
        type="primary"
        @click="handleSelectFromPreview"
        :disabled="isDocumentSelected(previewDocument)"
      >
        <CheckCircleOutlined />
        选择此文书
      </a-button>
    </a-space>
  </template>
</a-drawer>
```

**功能特性**：
- ✅ 显示文书的完整元数据（标题、类型、创建时间、ID）
- ✅ 文档 ID 支持一键复制
- ✅ 显示文书内容字数统计
- ✅ 使用 `<pre>` 标签保持原始格式（换行、缩进）
- ✅ 内容为空时显示友好提示
- ✅ 底部提供"关闭"和"选择此文书"按钮
- ✅ 如果文书已被选中，"选择此文书"按钮禁用

#### 2. 脚本部分（Script）

**位置**：第 343-368 行

**新增导入**：

```typescript
import {
  // ... 其他图标
  EyeOutlined  // 新增：预览图标
} from '@ant-design/icons-vue'

// 文书预览状态
const previewDrawerVisible = ref(false)
const previewDocument = ref<any>(null)
```

**位置**：第 480-516 行

**新增函数**：

```typescript
// 处理文书预览
const handlePreviewDocument = (doc: any) => {
  previewDocument.value = doc
  previewDrawerVisible.value = true
}

// 从预览中选择文书
const handleSelectFromPreview = () => {
  if (previewDocument.value) {
    handleSelectDocument(previewDocument.value)
    previewDrawerVisible.value = false
  }
}

// 获取文书内容
const getDocumentContent = (doc: any) => {
  if (!doc) return ''
  return doc.content || ''
}

// 获取文书内容长度
const getContentLength = (doc: any) => {
  const content = getDocumentContent(doc)
  return content ? content.length : 0
}
```

**函数说明**：
- `handlePreviewDocument`: 打开预览抽屉，设置当前预览的文书
- `handleSelectFromPreview`: 从预览界面直接选择文书并关闭抽屉
- `getDocumentContent`: 安全地获取文书内容，处理空值情况
- `getContentLength`: 计算文书内容的字符数

#### 3. 样式部分（Style）

**位置**：第 649-694 行

**新增样式**：

```less
// 文书预览抽屉样式
.document-preview {
  .document-info {
    margin-bottom: 24px;
  }

  .document-content-section {
    h4 {
      font-weight: 600;
      margin-bottom: 16px;
      color: #333;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .content-wrapper {
      background-color: #f5f5f5;
      border: 1px solid #d9d9d9;
      border-radius: 4px;
      padding: 16px;
      max-height: calc(100vh - 400px);
      overflow-y: auto;

      .content-text {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: 'Courier New', Courier, monospace;
        font-size: 14px;
        line-height: 1.8;
        color: #333;
      }
    }
  }
}
```

**样式特性**：
- ✅ 内容区域使用浅灰色背景，提升可读性
- ✅ 使用等宽字体（Courier New），适合显示病历内容
- ✅ `white-space: pre-wrap` 保持原始换行和空格
- ✅ `word-wrap: break-word` 防止长单词溢出
- ✅ 最大高度限制，超出部分可滚动
- ✅ 行高 1.8，提升阅读舒适度

## 用户交互流程

### 1. 预览文书

```
用户操作：点击文书列表项右侧的"眼睛"图标
↓
系统响应：从右侧滑出预览抽屉
↓
显示内容：
  - 文书标题、类型、创建时间、ID
  - 文书完整内容（保持原始格式）
  - 内容字数统计
```

### 2. 从预览中选择文书

```
用户操作：在预览抽屉底部点击"选择此文书"按钮
↓
系统响应：
  - 调用 handleSelectDocument() 选择文书
  - 关闭预览抽屉
  - 显示成功提示消息
```

### 3. 关闭预览

```
用户操作：
  - 点击"关闭"按钮
  - 或点击抽屉外部区域
  - 或按 ESC 键
↓
系统响应：关闭预览抽屉，返回文书列表
```

## 技术亮点

### 1. 事件冒泡处理

使用 `@click.stop` 阻止预览按钮的点击事件冒泡到列表项，避免同时触发文书选择：

```vue
<a-button @click.stop="handlePreviewDocument(item)">
```

### 2. 安全的数据访问

所有数据访问都进行了空值检查，避免运行时错误：

```typescript
const getDocumentContent = (doc: any) => {
  if (!doc) return ''
  return doc.content || ''
}
```

### 3. 响应式布局

抽屉宽度设置为 720px，在大屏幕上提供舒适的阅读体验，同时不会完全遮挡主界面。

### 4. 性能优化

- 使用 `v-if` 条件渲染，只在打开抽屉时渲染内容
- 内容区域设置最大高度并启用滚动，避免长文本导致页面卡顿

## 测试验证

### 测试步骤

1. **启动服务**：
   ```bash
   # 确保前后端服务都在运行
   # 后端：http://localhost:8000
   # 前端：http://localhost:3000
   ```

2. **进入质控演示页面**：
   - 访问：http://localhost:3000/demo/qc-demo
   - 或从导航菜单选择"质控演示"

3. **选择病历**：
   - 在左侧病历列表中选择一条病历（例如：刘德华）
   - 等待右侧加载该病历的文书列表

4. **预览文书**：
   - 在右侧"可用文书"列表中，点击"首次病程记录"右侧的"眼睛"图标
   - 验证预览抽屉从右侧滑出
   - 验证显示文书的完整信息和内容

5. **验证功能**：
   - ✅ 文书标题、类型、创建时间正确显示
   - ✅ 文档 ID 可以复制
   - ✅ 内容字数统计正确
   - ✅ 文书内容保持原始格式（换行、缩进）
   - ✅ 长文本可以滚动查看
   - ✅ 点击"选择此文书"按钮可以选择文书并关闭抽屉
   - ✅ 点击"关闭"按钮可以关闭抽屉
   - ✅ 如果文书已被选中，"选择此文书"按钮禁用

6. **测试边界情况**：
   - 预览没有内容的文书（应显示"该文书暂无内容"）
   - 预览超长内容的文书（应启用滚动）
   - 连续预览多个文书（应正确切换内容）

## 后续优化建议

### 1. 性能优化

如果文书内容超过 10000 字，可以考虑：
- 只显示前 5000 字，提供"查看完整内容"按钮
- 使用虚拟滚动技术优化长文本渲染

### 2. 功能增强

- 添加文书内容搜索功能（Ctrl+F）
- 支持文书内容导出（复制、下载）
- 添加文书内容高亮显示（关键词、诊断、药品等）
- 支持文书内容打印

### 3. 用户体验

- 添加加载动画（如果文书内容需要异步加载）
- 支持键盘快捷键（ESC 关闭、← → 切换文书）
- 记住用户的预览偏好（抽屉宽度、字体大小等）

## 相关文件

- ✅ **已修改**：`health-qc-monorepo/apps/medqc-web/src/components/demo/TargetSelectionStep.vue`
- **数据来源**：`health-qc-monorepo/apps/medqc-web/backend/app/routers/records.py`（返回文书的 `content` 字段）
- **状态管理**：`health-qc-monorepo/apps/medqc-web/src/stores/qcDemo.ts`

## 总结

✅ **功能已完成**：在质控演示页面的文书选择步骤中，成功添加了文书内容预览功能。

✅ **用户体验提升**：用户可以在选择文书之前预览内容，做出更准确的选择。

✅ **技术实现优雅**：使用 Ant Design Vue 的 Drawer 组件，代码简洁，易于维护。

✅ **无副作用**：不影响现有的文书选择功能，完全向后兼容。

