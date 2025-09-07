# 医疗质控系统 UI 设计规范文档

## 文档概述

本文档基于质控规则管理页面的优化实践，制定了医疗质控系统的统一UI设计规范。所有团队成员在开发过程中必须严格遵循本规范，确保系统界面的一致性和专业性。

---

## 1. 字体规范

### 1.1 字体层次体系

| 层级 | 用途 | 字体大小 | 字重 | 颜色 | 应用场景 |
|------|------|----------|------|------|----------|
| **H1** | 页面主标题 | 16px | Bold (700) | #111827 | 页面顶部标题 |
| **H2** | 统计卡片标题 | 15px | Bold (700) | #374151 | 数据统计标题 |
| **H3** | 卡片标题 | 14px | SemiBold (600) | #374151 | 功能区域标题 |
| **Body-L** | 头部按钮 | 13px | Medium (500) | - | 主要操作按钮 |
| **Body-M** | 正文内容 | 12px | Normal (400) | #374151 | 表格内容、筛选控件 |
| **Body-S** | 辅助文本 | 11px | Normal (400) | #6B7280 | 表格标题、标签文字 |
| **Caption** | 说明文字 | 10px | Normal (400) | #9CA3AF | 提示信息、状态说明 |

### 1.2 特殊文本规范

#### 数据展示文字
- **统计数字**: 20px, Bold (700)
- **表格数值**: 12px, Normal (400)
- **权重数值**: 12px, Medium (500)

#### 交互元素文字
- **链接按钮**: 12px, Normal (400), 蓝色主题色
- **操作按钮**: 12px, Medium (500)
- **标签文字**: 11px, Normal (400)

---

## 2. 组件尺寸规范

### 2.1 按钮规范

#### 主要按钮（头部操作区域）
```css
height: 30px
padding: 4px 14px
font-size: 13px
font-weight: 500
border-radius: 4px
```

#### 次要按钮（筛选区域）
```css
height: 28px
padding: 3px 12px
font-size: 12px
font-weight: 400
border-radius: 4px
```

#### 小按钮（表格内操作）
```css
height: 22px
padding: 0px 6px
font-size: 12px
font-weight: 400
border-radius: 2px
```

### 2.2 输入框规范

#### 标准输入框（筛选区域）
```css
height: 28px
padding: 3px 8px
font-size: 12px
border-radius: 4px
border: 1px solid #D1D5DB
```

#### 搜索输入框
```css
height: 28px
padding: 3px 8px
font-size: 12px
border-radius: 4px
```

### 2.3 下拉菜单规范

#### 选择器
```css
height: 28px
padding: 0 8px
font-size: 12px
border-radius: 4px
```

#### 选项
```css
line-height: 26px
font-size: 12px
padding: 4px 8px
```

### 2.4 标签和徽章规范

#### 状态标签
```css
height: 18px
padding: 0 5px
font-size: 11px
line-height: 16px
border-radius: 2px
margin: 0 2px 2px 0
```

#### 开关组件
```css
height: 16px
min-width: 28px
font-size: 10px
```

---

## 3. 布局间距规范

### 3.1 页面级间距

#### 页面容器
```css
padding: 16px  /* 页面四周边距 */
```

#### 区域间距
- **页面标题到统计卡片**: 16px
- **统计卡片到筛选区域**: 16px  
- **筛选区域到表格**: 16px
- **卡片之间间距**: 12px

### 3.2 组件级间距

#### 统计卡片网格
```css
gap: 12px  /* 卡片间距 */
margin-bottom: 16px
```

#### 按钮组间距
```css
gap: 8px   /* 头部按钮组 */
gap: 6px   /* 筛选区域按钮组 */
gap: 3px   /* 表格内操作按钮 */
```

### 3.3 文本间距
- **标题到内容**: 8px
- **段落间距**: 12px
- **列表项间距**: 4px

---

## 4. 表格设计规范

### 4.1 表格结构规范

#### 表格行高
```css
表格标题行: 40px
表格内容行: 36px (固定高度)
```

#### 单元格内边距
```css
标题单元格: 8px 6px
普通单元格: 4px 8px
质控点列单元格: 3px 6px  /* 特殊紧凑处理 */
```

### 4.2 列宽分配标准

| 列名 | 宽度 | 说明 |
|------|------|------|
| 规则编码 | 90px | 固定宽度，显示编码 |
| 质控点来源 | 180px | 中等宽度，显示来源名称 |
| 质控点名称 | 220px | 较宽，显示详细描述 |
| 分类 | 80px | 紧凑，显示标签 |
| 严重程度 | 90px | 适中，显示标签 |
| 类型 | 80px | 紧凑，显示标签 |
| 最大扣分 | 85px | 适中，显示数值 |
| 权重 | 60px | 紧凑，显示数值 |
| 状态 | 60px | 紧凑，显示开关 |
| 操作 | 120px | 固定，显示操作按钮 |

### 4.3 表格字体规范
- **表格标题**: 11px, SemiBold (600), 不换行
- **表格内容**: 12px, Normal (400)
- **质控点来源**: 12px, Medium (500)
- **质控点名称**: 11px, Normal (400)

---

## 5. 卡片和容器规范

### 5.1 卡片内边距规范

#### 统计卡片
```css
padding: 16px 20px
border-radius: 6px
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1)
```

#### 筛选卡片
```css
padding: 12px 16px
border-radius: 6px
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1)
```

#### 表格卡片
```css
padding: 12px
border-radius: 6px
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1)
```

### 5.2 卡片布局规则

#### 统计卡片网格
- **桌面端**: 4列网格 (lg:grid-cols-4)
- **平板端**: 2列网格 (md:grid-cols-2)  
- **移动端**: 1列网格 (grid-cols-1)

#### 卡片间距
- **水平间距**: 12px
- **垂直间距**: 16px

---

## 6. 颜色规范

### 6.1 文字颜色
- **主要文字**: #111827 (gray-900)
- **次要文字**: #374151 (gray-700)
- **辅助文字**: #6B7280 (gray-500)
- **说明文字**: #9CA3AF (gray-400)

### 6.2 背景颜色
- **页面背景**: #F9FAFB (gray-50)
- **卡片背景**: #FFFFFF (white)
- **表格标题背景**: #F9FAFB (gray-50)
- **悬停背景**: #EFF6FF (blue-50)

### 6.3 边框颜色
- **默认边框**: #D1D5DB (gray-300)
- **输入框边框**: #D1D5DB (gray-300)
- **卡片边框**: #E5E7EB (gray-200)

---

## 7. 响应式设计规范

### 7.1 断点定义
- **移动端**: < 768px
- **平板端**: 768px - 1024px
- **桌面端**: > 1024px

### 7.2 响应式调整原则
1. **移动端优先**: 所有组件先适配移动端
2. **渐进增强**: 逐步适配更大屏幕
3. **内容优先**: 确保核心内容在所有设备上可访问
4. **操作便利**: 保证触摸操作的便利性

---

## 8. 实施指南

### 8.1 CSS 类命名规范
```css
/* 使用 Tailwind CSS 工具类 */
.page-container { @apply p-4; }
.page-header { @apply flex items-center justify-between mb-4; }
.stats-grid { @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4; }
```

### 8.2 组件开发原则
1. **一致性**: 严格遵循本规范的尺寸和间距
2. **可复用性**: 创建可复用的组件库
3. **可维护性**: 使用语义化的类名和结构
4. **可访问性**: 确保符合 WCAG 2.1 AA 标准

### 8.3 质量检查清单
- [ ] 字体大小符合层次规范
- [ ] 组件尺寸符合标准规格
- [ ] 间距使用规范数值
- [ ] 颜色使用系统色板
- [ ] 响应式布局正常
- [ ] 交互状态完整

---

## 9. 更新日志

| 版本 | 日期 | 更新内容 | 更新人 |
|------|------|----------|--------|
| v1.0 | 2024-08-27 | 初始版本，基于质控规则管理页面优化制定 | 开发团队 |

---

## 10. 附录

### 10.1 常用 CSS 代码片段
```css
/* 统计卡片标题样式 */
.stat-title {
  font-size: 15px;
  font-weight: 700;
  color: #374151;
  margin-bottom: 8px;
}

/* 表格标题样式 */
.table-header {
  font-size: 11px;
  font-weight: 600;
  padding: 8px 6px;
  white-space: nowrap;
}

/* 筛选按钮样式 */
.filter-button {
  height: 28px;
  padding: 3px 12px;
  font-size: 12px;
  border-radius: 4px;
}
```

### 10.2 Ant Design Vue 组件样式覆盖示例

```css
/* 深度选择器样式覆盖示例 */
:deep(.ant-statistic-title) {
  font-size: 15px !important;
  font-weight: 700 !important;
  color: #374151 !important;
  margin-bottom: 8px !important;
}

:deep(.ant-table-thead > tr > th) {
  font-size: 11px !important;
  font-weight: 600 !important;
  padding: 8px 6px !important;
  white-space: nowrap !important;
}

:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.ant-tag) {
  font-size: 11px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
  border-radius: 2px !important;
}

:deep(.ant-switch) {
  font-size: 10px !important;
  height: 16px !important;
  min-width: 28px !important;
}
```

### 10.3 Vue 组件模板示例

```vue
<template>
  <!-- 页面容器 -->
  <div class="page-container">

    <!-- 页面标题区域 -->
    <div class="page-header">
      <h1 class="page-title">质控规则管理</h1>
      <div class="header-actions">
        <a-button type="default">刷新</a-button>
        <a-button type="primary">新增规则</a-button>
      </div>
    </div>

    <!-- 统计卡片区域 -->
    <div class="stats-grid">
      <a-card class="stat-card">
        <a-statistic title="总规则数" :value="6" />
      </a-card>
      <!-- 更多统计卡片... -->
    </div>

    <!-- 筛选区域 -->
    <a-card class="filter-card">
      <a-space>
        <a-input-search placeholder="搜索规则名称" style="width: 200px" />
        <a-select placeholder="选择分类" style="width: 120px">
          <a-select-option value="all">全部分类</a-select-option>
        </a-select>
        <a-button>重置</a-button>
      </a-space>
    </a-card>

    <!-- 表格区域 -->
    <a-card class="rules-table-card">
      <a-table
        :columns="columns"
        :data-source="data"
        size="middle"
        :pagination="pagination"
      />
    </a-card>

  </div>
</template>
```

### 10.4 设计工具配置
- **字体**: 系统默认字体栈 (-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif)
- **设计软件**: Figma/Sketch
- **开发框架**: Vue 3 + Ant Design Vue + Tailwind CSS
- **CSS 预处理器**: PostCSS
- **构建工具**: Vite

### 10.5 浏览器兼容性
- **现代浏览器**: Chrome 88+, Firefox 85+, Safari 14+, Edge 88+
- **移动浏览器**: iOS Safari 14+, Chrome Mobile 88+
- **不支持**: Internet Explorer

### 10.6 性能优化建议
1. **CSS 优化**: 使用 Tailwind CSS 的 purge 功能移除未使用的样式
2. **字体加载**: 使用 font-display: swap 优化字体加载
3. **组件懒加载**: 大型表格使用虚拟滚动
4. **图标优化**: 使用 SVG 图标替代字体图标

---

## 11. 常见问题解答

### Q1: 为什么表格标题字体这么小？
A1: 11px 的表格标题字体确保了在有限的表格宽度内能够显示完整的标题文字，避免换行影响表格整体美观。同时通过 600 的字重保证了可读性。

### Q2: 统计卡片标题为什么要用 15px 粗体？
A2: 统计卡片是页面的关键信息展示区域，15px 粗体能够有效吸引用户注意力，突出数据的重要性，形成良好的视觉层次。

### Q3: 为什么要区分头部按钮和筛选按钮的尺寸？
A3: 头部按钮承载主要操作功能，需要更突出的视觉重量；筛选按钮属于辅助功能，使用较小尺寸可以节省空间，让用户专注于内容本身。

### Q4: 如何确保在不同设备上的一致性？
A4: 通过响应式设计和相对单位确保在不同设备上的适配，同时保持核心的字体层次和间距比例不变。

---

## 12. 团队协作规范

### 12.1 设计师职责
- 严格按照本规范创建设计稿
- 标注具体的字体大小、间距数值
- 提供不同状态下的组件样式
- 确保设计稿的响应式适配方案

### 12.2 前端开发职责
- 严格按照规范实现组件样式
- 使用规范中定义的 CSS 类和数值
- 确保组件的可复用性和一致性
- 进行跨浏览器兼容性测试

### 12.3 测试职责
- 验证界面元素是否符合规范要求
- 检查不同设备和浏览器的显示效果
- 确保交互体验的一致性
- 反馈规范执行中的问题

### 12.4 项目管理职责
- 确保团队成员了解并遵循规范
- 定期组织规范培训和分享
- 收集规范使用反馈并推动改进
- 维护规范文档的更新和版本管理

---

*本文档将根据项目发展和用户反馈持续更新完善。如有疑问或建议，请联系开发团队。*

**文档维护**: 开发团队
**最后更新**: 2024-08-27
**版本**: v1.0
