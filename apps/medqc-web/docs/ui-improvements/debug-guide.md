# 文档选择功能调试指南

## 🔍 当前调试状态

我已经在代码中添加了详细的调试信息，现在可以通过浏览器控制台查看文档选择的完整流程。

## 📋 调试步骤

### 1. 打开测试页面
访问: http://localhost:3000/test-document-selection.html

### 2. 进入医疗记录详情页面
1. 点击测试页面上的"打开医疗记录详情页面进行测试"按钮
2. 在新打开的页面中点击"增强视图"按钮

### 3. 打开开发者工具
按 F12 键打开开发者工具，切换到 Console 标签页

### 4. 测试文档选择
在右侧文档分类区域点击任意文档，观察控制台输出

## 🔍 预期的调试信息流程

当您点击一个文档时，应该看到以下调试信息序列：

### 步骤 1: Tree 选择事件
```
=== Tree onSelect 调试 ===
选中的keys: ["doc-xxx"]
节点信息: {key: "doc-xxx", title: "首次病程记录", isCategory: false, ...}
是否为分类: false
是否有document: true
调用 selectDocument
```

### 步骤 2: 组件内部选择处理
```
=== EnhancedDocumentClassification selectDocument ===
选中的文档: {type: "first_progress_note", title: "首次病程记录", ...}
文档ID: undefined (可能没有ID)
文档类型: first_progress_note
已发送 document-select 事件
```

### 步骤 3: 父组件处理
```
=== 文档选择调试信息 ===
选择的文档: {type: "first_progress_note", title: "首次病程记录", ...}
文档类型: first_progress_note
文档标题: 首次病程记录
是否有content: false
是否有content_preview: true
当前record状态: true
```

### 步骤 4: 内容更新
```
=== 内容更新调试信息 ===
设置的内容长度: 123
设置的标题: 首次病程记录 (预览)
内容前100字符: 患者张伟，性别男，年龄44岁，以"发现肛旁肿物疼痛2+天"为主诉...
```

## 🐛 常见问题诊断

### 问题 1: 没有任何调试信息
**可能原因:**
- 没有在增强视图模式下
- 点击的是分类文件夹而非具体文档
- 事件绑定有问题

**解决方法:**
1. 确认页面顶部显示"增强视图"按钮为激活状态
2. 确认点击的是文档名称，不是文件夹图标
3. 刷新页面重试

### 问题 2: 只有前面的调试信息，没有后续的
**可能原因:**
- 事件传递中断
- 父组件的 handleDocumentSelect 函数没有被调用

**解决方法:**
1. 检查控制台是否有错误信息
2. 确认组件的事件绑定是否正确

### 问题 3: 有调试信息但内容不更新
**可能原因:**
- 内容绑定有问题
- Vue 响应式更新失败

**解决方法:**
1. 检查 "内容更新调试信息" 中的内容长度是否大于0
2. 检查左侧内容查看器的 props 绑定

### 问题 4: 内容长度为0
**可能原因:**
- 文档数据中没有 content 或 content_preview
- 从原始文本提取失败

**解决方法:**
1. 检查文档数据结构
2. 检查 extractDocumentFromRawText 函数的逻辑

## 🔧 手动测试方法

如果自动测试有问题，可以手动测试：

### 1. 直接调用函数
在控制台中执行：
```javascript
// 模拟文档数据
const testDoc = {
  type: 'first_progress_note',
  title: '首次病程记录',
  content_preview: '这是测试内容...'
};

// 直接调用处理函数（需要在Vue组件上下文中）
// 这个需要在实际页面的控制台中执行
```

### 2. 检查数据结构
```javascript
// 检查当前记录数据
console.log('当前记录:', window.record);

// 检查文档数据
console.log('文档列表:', window.record?.documents);
console.log('AI提取结果:', window.record?.ai_extraction_result);
```

## 📊 数据结构说明

### 文档数据结构
```javascript
{
  type: "first_progress_note",           // 文档类型
  title: "首次病程记录",                  // 文档标题
  content_preview: "患者张伟...",        // 内容预览
  content: undefined,                    // 完整内容（通常为空）
  confidence: 95,                        // AI分类置信度
  ai_classified: true                    // 是否AI分类
}
```

### 树形数据结构
```javascript
{
  key: "doc-xxx",                        // 节点唯一标识
  title: "首次病程记录",                  // 显示标题
  isCategory: false,                     // 是否为分类节点
  document: { /* 原始文档数据 */ },       // 文档数据
  confidence: 0.95,                      // 置信度
  aiClassified: true                     // AI分类标识
}
```

## ✅ 成功标准

当看到完整的调试信息流程且左侧内容确实更新时，说明功能正常工作。

## 📝 下一步

如果通过调试发现了具体问题，我们可以针对性地修复：

1. **事件传递问题**: 修复组件间的事件绑定
2. **数据结构问题**: 调整数据处理逻辑
3. **内容提取问题**: 优化文本提取算法
4. **响应式更新问题**: 修复Vue响应式绑定

请按照上述步骤进行测试，并将控制台的调试信息反馈给我，这样我就能准确定位问题所在。
