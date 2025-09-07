# UI 设计规范 - 快速参考卡片

## 🎯 字体大小速查表

| 元素类型 | 字体大小 | 字重 | 使用场景 |
|----------|----------|------|----------|
| 页面标题 | **16px** | Bold | 页面主标题 |
| 统计标题 | **15px** | Bold | 数据卡片标题 |
| 卡片标题 | **14px** | SemiBold | 功能区域标题 |
| 头部按钮 | **13px** | Medium | 主要操作按钮 |
| 正文内容 | **12px** | Normal | 表格内容、筛选控件 |
| 表格标题 | **11px** | SemiBold | 表格列标题 |
| 标签文字 | **11px** | Normal | 状态标签 |
| 说明文字 | **10px** | Normal | 提示信息 |

## 📏 组件尺寸速查表

### 按钮尺寸
```css
/* 头部按钮 */
height: 30px, padding: 4px 14px, font-size: 13px

/* 筛选按钮 */  
height: 28px, padding: 3px 12px, font-size: 12px

/* 表格按钮 */
height: 22px, padding: 0px 6px, font-size: 12px
```

### 输入框尺寸
```css
/* 标准输入框 */
height: 28px, padding: 3px 8px, font-size: 12px

/* 下拉菜单 */
height: 28px, padding: 0 8px, font-size: 12px
```

### 标签和开关
```css
/* 状态标签 */
height: 18px, padding: 0 5px, font-size: 11px

/* 开关组件 */
height: 16px, min-width: 28px, font-size: 10px
```

## 📐 间距速查表

### 页面级间距
- 页面容器: `padding: 16px`
- 区域间距: `16px`
- 卡片间距: `12px`

### 表格规范
- 表格行高: `36px`
- 标题单元格: `padding: 8px 6px`
- 普通单元格: `padding: 4px 8px`
- 质控点列: `padding: 3px 6px`

### 卡片内边距
- 统计卡片: `16px 20px`
- 筛选卡片: `12px 16px`
- 表格卡片: `12px`

## 🎨 颜色速查表

### 文字颜色
- 主要文字: `#111827` (gray-900)
- 次要文字: `#374151` (gray-700)  
- 辅助文字: `#6B7280` (gray-500)
- 说明文字: `#9CA3AF` (gray-400)

### 背景颜色
- 页面背景: `#F9FAFB` (gray-50)
- 卡片背景: `#FFFFFF` (white)
- 表格标题: `#F9FAFB` (gray-50)
- 悬停背景: `#EFF6FF` (blue-50)

## 📊 表格列宽参考

| 列名 | 宽度 | 说明 |
|------|------|------|
| 规则编码 | 90px | 固定宽度 |
| 质控点来源 | 180px | 中等宽度 |
| 质控点名称 | 220px | 较宽显示 |
| 分类 | 80px | 紧凑显示 |
| 严重程度 | 90px | 适中显示 |
| 类型 | 80px | 紧凑显示 |
| 最大扣分 | 85px | 数值显示 |
| 权重 | 60px | 紧凑数值 |
| 状态 | 60px | 开关显示 |
| 操作 | 120px | 按钮组 |

## 🔧 常用 CSS 类

### Tailwind 工具类
```css
/* 页面布局 */
.page-container { @apply p-4; }
.page-header { @apply flex items-center justify-between mb-4; }
.stats-grid { @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4; }

/* 文字样式 */
.page-title { @apply text-lg font-bold text-gray-900; }
.stat-title { @apply text-gray-700 font-bold; }
.table-header { @apply bg-gray-50 font-semibold; }
```

### Ant Design 覆盖
```css
/* 统计卡片 */
:deep(.ant-statistic-title) {
  font-size: 15px !important;
  font-weight: 700 !important;
}

/* 表格标题 */
:deep(.ant-table-thead > tr > th) {
  font-size: 11px !important;
  padding: 8px 6px !important;
  white-space: nowrap !important;
}

/* 按钮 */
:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
}

/* 输入框 */
:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
}
```

## ⚡ 快速检查清单

### 字体检查
- [ ] 页面标题使用 16px Bold
- [ ] 统计标题使用 15px Bold  
- [ ] 表格标题使用 11px SemiBold
- [ ] 正文内容使用 12px Normal
- [ ] 标签文字使用 11px Normal

### 尺寸检查
- [ ] 头部按钮高度 30px
- [ ] 筛选按钮高度 28px
- [ ] 输入框高度 28px
- [ ] 表格行高 36px
- [ ] 标签高度 18px

### 间距检查
- [ ] 页面容器 16px 内边距
- [ ] 区域间距 16px
- [ ] 卡片间距 12px
- [ ] 表格单元格内边距正确

### 响应式检查
- [ ] 移动端 1 列布局
- [ ] 平板端 2 列布局
- [ ] 桌面端 4 列布局
- [ ] 所有断点正常显示

## 🚀 开发提示

### 性能优化
1. 使用 Tailwind 的 purge 功能
2. 合理使用 `!important` 覆盖第三方样式
3. 避免深层嵌套选择器
4. 使用语义化的类名

### 兼容性注意
1. 测试主流浏览器显示效果
2. 确保移动端触摸操作便利
3. 检查高分辨率屏幕显示
4. 验证无障碍访问支持

### 维护建议
1. 定期检查规范执行情况
2. 收集用户反馈优化规范
3. 保持设计系统的一致性
4. 及时更新文档版本

---

**💡 提示**: 将此文档加入书签，开发时随时参考！

**📞 联系**: 如有疑问请联系开发团队  
**📅 更新**: 2024-08-27  
**📋 版本**: v1.0
