# 设计系统组件库规范

## 概述

本文档定义了医疗质控系统的设计组件库规范，为设计师提供标准化的设计元素和组件，确保设计稿与开发实现的一致性。

---

## 1. 设计令牌 (Design Tokens)

### 1.1 字体令牌

```json
{
  "font": {
    "size": {
      "xs": "10px",
      "sm": "11px",
      "base": "12px",
      "md": "13px",
      "lg": "14px",
      "xl": "15px",
      "2xl": "16px",
      "3xl": "20px"
    },
    "weight": {
      "normal": 400,
      "medium": 500,
      "semibold": 600,
      "bold": 700
    },
    "lineHeight": {
      "tight": 1.3,
      "normal": 1.4,
      "relaxed": 1.5
    }
  }
}
```

### 1.2 间距令牌

```json
{
  "spacing": {
    "xs": "2px",
    "sm": "4px",
    "base": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "20px",
    "2xl": "24px",
    "3xl": "32px"
  }
}
```

### 1.3 颜色令牌

```json
{
  "colors": {
    "gray": {
      "50": "#F9FAFB",
      "100": "#F3F4F6",
      "200": "#E5E7EB",
      "300": "#D1D5DB",
      "400": "#9CA3AF",
      "500": "#6B7280",
      "600": "#4B5563",
      "700": "#374151",
      "800": "#1F2937",
      "900": "#111827"
    },
    "blue": {
      "50": "#EFF6FF",
      "500": "#3B82F6",
      "600": "#2563EB"
    }
  }
}
```

---

## 2. 基础组件规范

### 2.1 按钮组件

#### 主要按钮 (Primary Button)

```
尺寸: 30px × auto
内边距: 4px 14px
字体: 13px Medium
圆角: 4px
颜色: Blue-600 背景, White 文字
状态: Normal, Hover, Active, Disabled
```

#### 次要按钮 (Secondary Button)

```
尺寸: 28px × auto
内边距: 3px 12px
字体: 12px Normal
圆角: 4px
颜色: Gray-100 背景, Gray-700 文字
状态: Normal, Hover, Active, Disabled
```

#### 小按钮 (Small Button)

```
尺寸: 22px × auto
内边距: 0px 6px
字体: 12px Normal
圆角: 2px
颜色: Transparent 背景, Blue-600 文字
状态: Normal, Hover, Active, Disabled
```

### 2.2 输入框组件

#### 标准输入框

```
尺寸: 28px × 200px (默认宽度)
内边距: 3px 8px
字体: 12px Normal
圆角: 4px
边框: 1px Gray-300
状态: Normal, Focus, Error, Disabled
占位符: Gray-400 文字
```

#### 搜索输入框

```
尺寸: 28px × 200px
内边距: 3px 8px 3px 32px (左侧图标空间)
字体: 12px Normal
圆角: 4px
图标: 搜索图标 16px Gray-400
```

### 2.3 下拉菜单组件

#### 选择器

```
尺寸: 28px × 120px (默认宽度)
内边距: 0 8px
字体: 12px Normal
圆角: 4px
边框: 1px Gray-300
箭头: 下拉箭头 12px Gray-400
状态: Normal, Focus, Open, Disabled
```

#### 选项列表

```
选项高度: 26px
选项内边距: 4px 8px
字体: 12px Normal
状态: Normal, Hover, Selected
```

### 2.4 标签组件

#### 状态标签

```
尺寸: 18px × auto
内边距: 0 5px
字体: 11px Normal
圆角: 2px
颜色变体:
- 完整性: Blue-100 背景, Blue-800 文字
- 一致性: Green-100 背景, Green-800 文字
- 合理性: Yellow-100 背景, Yellow-800 文字
- 及时性: Purple-100 背景, Purple-800 文字
```

### 2.5 开关组件

```
尺寸: 16px × 28px
圆角: 8px
滑块: 12px × 12px 圆形
状态: Off (Gray-300), On (Blue-600)
动画: 0.2s ease-in-out
```

---

## 3. 复合组件规范

### 3.1 统计卡片

```
容器:
- 内边距: 16px 20px
- 圆角: 6px
- 阴影: 0 1px 3px rgba(0,0,0,0.1)
- 背景: White

标题:
- 字体: 15px Bold
- 颜色: Gray-700
- 底边距: 8px

数值:
- 字体: 20px Bold
- 颜色: Gray-900
- 行高: 1.2
```

### 3.2 筛选卡片

```
容器:
- 内边距: 12px 16px
- 圆角: 6px
- 阴影: 0 1px 3px rgba(0,0,0,0.1)
- 背景: White

内容布局:
- 元素间距: 8px
- 垂直对齐: 居中
- 换行: 允许
```

### 3.3 表格组件

#### 表格容器

```
圆角: 6px
阴影: 0 1px 3px rgba(0,0,0,0.1)
背景: White
内边距: 12px
```

#### 表格标题行

```
高度: 40px
背景: Gray-50
字体: 11px SemiBold
颜色: Gray-700
内边距: 8px 6px
不换行: white-space: nowrap
```

#### 表格内容行

```
高度: 36px (固定)
背景: White
悬停背景: Blue-50
字体: 12px Normal
颜色: Gray-700
内边距: 4px 8px
垂直对齐: 居中
```

#### 特殊列样式

```
质控点来源列:
- 字体: 12px Medium
- 颜色: Gray-900
- 内边距: 3px 6px

质控点名称列:
- 字体: 11px Normal
- 颜色: Gray-700
- 内边距: 3px 6px
- 文本换行: 允许
```

---

## 4. 布局组件规范

### 4.1 页面容器

```
最大宽度: 100%
内边距: 16px
背景: Gray-50
最小高度: 100vh
```

### 4.2 页面标题区域

```
布局: Flex, 两端对齐
底边距: 16px
对齐: 垂直居中

标题:
- 字体: 16px Bold
- 颜色: Gray-900

操作区域:
- 按钮间距: 8px
- 对齐: 右对齐
```

### 4.3 网格布局

#### 统计卡片网格

```
桌面端: 4列网格
平板端: 2列网格
移动端: 1列网格
间距: 12px
底边距: 16px
```

#### 响应式断点

```
移动端: < 768px
平板端: 768px - 1024px
桌面端: > 1024px
```

---

## 5. 状态和交互规范

### 5.1 悬停状态 (Hover)

```
按钮: 背景色加深 10%
卡片: 阴影增强 (0 4px 12px rgba(0,0,0,0.15))
表格行: 背景色 Blue-50
链接: 颜色加深, 添加下划线
```

### 5.2 焦点状态 (Focus)

```
输入框: 边框色 Blue-500, 外发光 0 0 0 2px Blue-100
按钮: 外发光 0 0 0 2px Blue-100
下拉菜单: 边框色 Blue-500
```

### 5.3 激活状态 (Active)

```
按钮: 背景色加深 15%, 轻微内阴影
开关: 滑块位置改变, 背景色变化
标签: 背景色加深 5%
```

### 5.4 禁用状态 (Disabled)

```
按钮: 背景 Gray-100, 文字 Gray-400, 鼠标样式 not-allowed
输入框: 背景 Gray-50, 文字 Gray-400, 边框 Gray-200
下拉菜单: 背景 Gray-50, 文字 Gray-400
```

---

## 6. 图标规范

### 6.1 图标尺寸

```
小图标: 12px × 12px (表格内使用)
标准图标: 16px × 16px (按钮、输入框使用)
大图标: 20px × 20px (标题区域使用)
```

### 6.2 图标颜色

```
主要图标: Gray-600
次要图标: Gray-400
交互图标: Blue-600
状态图标: 根据状态颜色
```

### 6.3 常用图标

```
搜索: search
筛选: filter
刷新: refresh
新增: plus
编辑: edit
删除: delete
查看: eye
测试: play
导出: download
导入: upload
设置: settings
更多: more-horizontal
```

---

## 7. 动画和过渡

### 7.1 过渡时长

```
快速: 0.15s (按钮点击, 开关切换)
标准: 0.2s (悬停效果, 焦点状态)
慢速: 0.3s (模态框显示, 页面切换)
```

### 7.2 缓动函数

```
标准: ease-in-out (大多数过渡)
进入: ease-out (元素出现)
退出: ease-in (元素消失)
弹性: cubic-bezier(0.68, -0.55, 0.265, 1.55) (特殊效果)
```

### 7.3 动画属性

```
颜色变化: color, background-color, border-color
尺寸变化: width, height, padding, margin
位置变化: transform (translate, scale, rotate)
透明度: opacity
阴影: box-shadow
```

---

## 8. 设计工具配置

### 8.1 Figma 配置

#### 颜色样式 (Color Styles)

```
Primary/Gray-900: #111827
Primary/Gray-700: #374151
Primary/Gray-500: #6B7280
Primary/Gray-400: #9CA3AF
Primary/Gray-300: #D1D5DB
Primary/Gray-200: #E5E7EB
Primary/Gray-100: #F3F4F6
Primary/Gray-50: #F9FAFB
Primary/Blue-600: #2563EB
Primary/Blue-500: #3B82F6
Primary/Blue-50: #EFF6FF
```

#### 文本样式 (Text Styles)

```
Heading/H1: 16px Bold
Heading/H2: 15px Bold
Heading/H3: 14px SemiBold
Body/Large: 13px Medium
Body/Medium: 12px Normal
Body/Small: 11px Normal
Caption: 10px Normal
```

#### 效果样式 (Effect Styles)

```
Card Shadow: 0 1px 3px rgba(0,0,0,0.1)
Card Shadow Hover: 0 4px 12px rgba(0,0,0,0.15)
Focus Ring: 0 0 0 2px #DBEAFE
```

### 8.2 组件库结构

```
📁 Design System
  📁 Foundations
    📄 Colors
    📄 Typography
    📄 Spacing
    📄 Icons
  📁 Components
    📁 Basic
      📄 Button
      📄 Input
      📄 Select
      📄 Tag
      📄 Switch
    📁 Composite
      📄 StatCard
      📄 FilterCard
      📄 Table
    📁 Layout
      📄 PageContainer
      📄 PageHeader
      📄 Grid
  📁 Templates
    📄 RulesManagement
    📄 Dashboard
```

---

## 9. 交付规范

### 9.1 设计稿标注

#### 必须标注项

- 字体大小和字重
- 颜色值 (使用设计令牌名称)
- 间距和内边距数值
- 组件尺寸 (宽度、高度)
- 圆角半径
- 阴影参数

#### 标注格式

```
字体: Body/Medium (12px Normal)
颜色: Primary/Gray-700 (#374151)
间距: Spacing/MD (12px)
圆角: 4px
阴影: Card Shadow
```

### 9.2 切图规范

#### 图标切图

- 格式: SVG (矢量图标)
- 尺寸: 16×16px, 20×20px, 24×24px
- 颜色: 单色 (可通过 CSS 修改)
- 命名: icon-name-size.svg

#### 图片切图

- 格式: WebP (优先), PNG (备选)
- 分辨率: 1x, 2x, 3x
- 压缩: 保持质量前提下最小文件
- 命名: image-name@2x.webp

### 9.3 组件文档

每个组件需要提供:

- 组件预览图
- 使用场景说明
- 属性和状态列表
- 代码示例
- 设计决策说明

---

**📋 检查清单**

设计师交付前检查:

- [ ] 使用了正确的设计令牌
- [ ] 组件尺寸符合规范
- [ ] 标注信息完整准确
- [ ] 提供了所有必要状态
- [ ] 响应式适配方案清晰
- [ ] 切图资源完整

**🔄 版本控制**

- 主版本: 重大设计变更
- 次版本: 新增组件或功能
- 修订版本: 细节调整和修复

---

**📞 联系方式**: 设计团队  
**📅 更新日期**: 2024-08-27  
**📋 当前版本**: v1.0
