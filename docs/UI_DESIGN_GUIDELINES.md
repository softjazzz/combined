# UI 设计规范（历史初稿）

> 本文保留早期演示系统的视觉规范。现行 MedQC 工作台遵循 [Workstation v7.1 设计规范](../apps/medqc-web/docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md)，公共样式见 [设计变量](../apps/medqc-web/src/styles/tokens-v2.css) 和 [组件样式](../apps/medqc-web/src/styles/mq-components.css)。

> 目标：为 LLM 质控演示系统建立统一的视觉语言，使界面与医疗 dashboard 风格保持 80% 以上一致性，便于后续开发落地。

## 1. 品牌与色彩体系

### 1.1 主色调（Medical Blue Palette）

| 用途 | 色值 | 备注 |
| --- | --- | --- |
| Primary Base | `#0B64D4` | 主要按钮、关键高亮背景 |
| Primary Light | `#1E88FF` | 卡片渐变起始色、Hover 背景 |
| Primary Dark | `#084C9E` | 按钮 Press/Active、图标强调 |
| Primary Subtle | `#E6F4FF` | 选中状态背景、提示条背景 |

### 1.2 状态色

| 状态 | Base | Light | Dark | 用途 |
| --- | --- | --- | --- | --- |
| 成功 Success | `#52C41A` | `#E8F8E5` | `#389E0D` | 通过、正常状态标签 |
| 警告 Warning | `#FAAD14` | `#FFF7E6` | `#D48806` | 待处理、跟进提醒 |
| 失败 Error | `#F5222D` | `#FFF1F0` | `#CF1322` | 错误提示、风险警示 |
| 信息 Info | `#2C8EAA` | `#E6F7FF` | `#1677FF` | 信息提示、辅助标签 |

### 1.3 中性色与背景

| 名称 | 色值 | 说明 |
| --- | --- | --- |
| Text Primary | `#1F1F1F` | 标题、重要信息 |
| Text Secondary | `#595959` | 正文、次级信息 |
| Text Tertiary | `#8C8C8C` | 辅助文字、占位符 |
| Divider | `#E5E7EB` | 分割线、边框 |
| Page Background | `#F5F7FB` | 页面背景（浅灰蓝） |
| Card Background | `#FFFFFF` | 卡片与内容容器 |

## 2. 排版体系

### 2.1 字体家族

**标准字体栈**：
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
```

**等宽字体**（用于代码、病历文本、数据输出）：
```css
font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
```

**备选方案**：
- 中文优先：`Source Han Sans SC` / `思源黑体`
- 英文优先：`Inter`, `Roboto`

### 2.2 字号层级与应用规范

#### 标题层级

| 层级 | 字号 | 字重 | 行高 | 用途示例 | 颜色 |
| --- | --- | --- | --- | --- | --- |
| **H1 - 页面主标题** | 20px | 600 | 1.4 | 质控规则管理、批量质控评估 | `#262626` |
| **H2 - 区域标题** | 18px | 600 | 1.5 | 病历类型选择、测试结果 | `#262626` |
| **H3 - 模块标题** | 16px | 600 | 1.5 | 选择质控点、文书类型卡片 | `#333` |
| **H4 - 小标题** | 14px | 600 | 1.5 | 问题列表标题、分组标题 | `#333` |

#### 正文与内容层级

| 层级 | 字号 | 字重 | 行高 | 用途示例 | 颜色 |
| --- | --- | --- | --- | --- | --- |
| **强调文本** | 14px | 600 | 1.5 | 规则ID、重要标识 | `#1890ff` / `#333` |
| **次要强调** | 14px | 500 | 1.5 | 规则名称、卡片标签 | `#333` |
| **正文内容** | 14px | 400 | 1.6 | 描述文字、Tab文字、按钮文字 | `#262626` / `#595959` |
| **辅助信息** | 13px | 400 | 1.5 | 证据文字、小号ID | `#666` / `#1890ff` |
| **补充信息** | 12px | 400 | 1.5 | 计数标签、置信度、提示文字 | `#8c8c8c` |

#### 特殊用途字体

| 用途 | 字号 | 字重 | 字体家族 | 说明 |
| --- | --- | --- | --- | --- |
| **病历文本编辑器** | 14px | 400 | 等宽字体 | 便于阅读和对齐 |
| **LLM输出内容** | 12px | 400 | 等宽字体 | 保留格式和缩进 |
| **导航Tab** | 14px | 400/500 | 标准字体 | 常规400，激活500 |
| **图标** | 16-20px | - | Icon Font | 与文字对齐 |

### 2.3 字体使用规则

#### ✅ 正确做法

1. **明确声明字号和字重**：每个文本元素都应该有明确的 `font-size` 和 `font-weight`
2. **统一颜色变量**：使用 `#262626` / `#333` / `#595959` / `#8c8c8c` 等标准色
3. **保持层级清晰**：标题、正文、辅助文字有明显的大小和粗细差异
4. **等宽字体专用**：代码和数据展示必须使用等宽字体
5. **响应式调整**：移动端可适当缩小字号（-2px）

#### ❌ 错误做法

1. ~~依赖浏览器默认字号~~：必须明确设置
2. ~~混用多种字重~~：只使用 400（常规）、500（中等）、600（加粗）
3. ~~不统一的辅助色~~：避免 `#999` / `#666` / `#888` 等随意颜色
4. ~~正文使用等宽字体~~：等宽字体仅用于特殊场景
5. ~~忽略行高~~：所有文本必须设置合适的 `line-height`

### 2.4 实际应用示例

#### 批量质控评估页面字体使用

```less
// 根元素字体
.batch-rule-test {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
               'PingFang SC', 'Microsoft YaHei', sans-serif;
}

// 页面主标题
.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #262626;
  line-height: 1.4;
}

// 描述文字
.header-description {
  font-size: 14px;
  font-weight: 400;
  color: #8c8c8c;
  line-height: 1.5;
}

// 卡片标签
.card-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

// 辅助计数
.card-count {
  font-size: 12px;
  font-weight: 400;
  color: #8c8c8c;
}

// 病历文本（等宽字体）
.medical-textarea {
  font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.6;
}

// 规则ID（强调）
.rule-id {
  font-size: 13px;
  font-weight: 600;
  color: #1890ff;
}

// 规则名称（正文）
.rule-name {
  font-size: 14px;
  font-weight: 400;
  color: #333;
}
```

## 3. 间距与圆角

- **基础间距**：采用 8px 网格系统，常用 spacing：4 / 8 / 12 / 16 / 24 / 32px。
- **卡片内边距**：16px；卡片之间保持 16px 外边距。
- **按钮内边距**：水平 16px，垂直 8px（大按钮 12px）。
- **圆角规范**：
  - 卡片、列表容器：12px
  - 按钮、输入框：20px（胶囊风格）
  - 标签、状态标识：999px（全圆角）

## 4. 组件样式规范

### 4.1 按钮（Button）

| 类型 | 背景色 | 文本色 | 边框 | Hover | Disabled |
| --- | --- | --- | --- | --- | --- |
| Primary | `#FFFFFF` | `#0B64D4` | `#FFFFFF` | 背景 `#F2F6FF`，文字 `#084C9E` | 背景 `#DDE7FF`，文字 `#7AA5E9` |
| Secondary | `#FFFFFF` | `#0B64D4` | `#0B64D4` | 背景 `#E6F4FF` | 背景 `#F5F5F5`，文字 `#BFBFBF` |
| Text Button | 透明 | `#0B64D4` | 无 | 文本 `#084C9E` | 文本 `#BFBFBF` |

> 按钮组使用 Ant Design `ButtonGroup`，间距通过 `Space` 控制，保持 8px 基础间距。

### 4.2 卡片（Card）

- 背景：`#FFFFFF`
- 阴影：`0 6px 18px rgba(14, 110, 209, 0.08)` 或浅灰 `0 2px 10px rgba(15, 23, 42, 0.08)`
- 标题区：字号 16px，字重 600，底部 12px 分隔线（可使用 `border-bottom`）。
- 统计卡片可使用蓝色渐变背景，内置半透明圆形作为视觉重心。

### 4.3 列表 / 表格（List & Table）

- 行高：48px ± 4px。
- 选中态：背景 `#E6F4FF`，边框 `#1890FF`，可配合左侧色条或阴影。
- Hover：背景 `#F0F5FF`。
- 操作列：按钮使用 `Text Button` 样式（蓝色文字+icon）。
- 空态 `Empty` 组件需附带操作按钮（如“重置筛选”）。

### 4.4 表单控件

- 输入框背景 `#FFFFFF`，边框 `#D9D9D9`，圆角 20px。
- Focus 状态：边框 `#0B64D4`，阴影 `0 0 0 3px rgba(24, 144, 255, 0.2)`。
- 下拉框与选择器：使用浅透明白背景，选项 hover `#E6F4FF`。

### 4.5 标签（Tag / Badge）

- 使用状态色 + 全圆角。
- 内边距：水平 8px，垂直 2px；字号 12px。
- 图标与文字间距 4px。

### 4.6 空态与加载

- 空态统一采用 `Empty.PRESENTED_IMAGE_SIMPLE`，描述文字 14px，次级文本 12px。
- 必须提供一个 CTA（按钮或链接）帮助用户“重置筛选 / 前往数据源”。
- 数据加载使用 `Spin` 包裹局部区域，避免整屏闪烁。

### 4.7 标签页（Tabs）

- 使用 `Tabs` 的 `card` 模式并自定义为胶囊样式，圆角 20px、间距 12px。
- 默认态文字 `@color-text-secondary`，Hover 背景 `rgba(11, 100, 212, 0.08)`。
- 选中态背景 `@color-primary-subtle`，描边 `rgba(11, 100, 212, 0.25)`，文字使用 `@color-primary`。
- 左侧可配合 16px 图标，图标与文本间距 8px，确保视觉重心一致。

### 4.8 筛选条（Filter Bar）

- 结构：外层使用浅色背景 `@color-bg-page` 的加深版本（如 `rgba(11, 100, 212, 0.12)`），圆角 12px。
- 内边距 16px，行间距使用 `Row` 的 `[16, 16]` gutter，移动端需自动换行。
- 输入框、选择器统一圆角 24px，左右内边距 12px，前缀图标颜色 `@color-text-tertiary`。
- 常规按钮采用 `Space` + `wrap` 方式排布，保持 8~16px 基础间距。

### 4.9 表格操作与链接按钮

- 表格主体圆角 12px，Hover 行背景 `@color-primary-subtle`。
- 操作列使用 `link` 按钮样式，基色对应操作类型：
  - 主操作：`@color-primary`
  - 风险/停用：`@color-warning`
  - 成功/激活：`@color-success`
  - 删除：`@color-error`
- 标签（如角色标签）使用淡色背景（`@color-primary-subtle` 等）+ 圆角 999px，字号 12px。

### 4.10 步骤指示器与流程卡片

- 流程步骤统一使用 `Steps` 组件，圆形图标尺寸 36px，当前步骤采用医疗蓝渐变（Primary → Primary Dark），已完成步骤描边 `rgba(11, 100, 212, 0.4)`。
- 步骤容器使用白底卡片，圆角 16px、内边距 24px、阴影 `var(--shadow-light)`，外边框 `rgba(11, 100, 212, 0.08)`。
- 步骤内容卡片保持同规格圆角与阴影，切换时可使用 `fadeInUp` 0.35s 动画提升动效体验。
- 关联的控制面板、辅助信息面板应采用相同卡片体系，模块间保持 20px 间距。

## 5. 布局与导航

### 5.1 主框架

- 遵循 24 栅格系统：
  - 典型页面采用 6 / 18 或 8 / 16 黄金比例（如病历列表 + 文书详情）。
  - 移动端（≤768px）自动折叠为单列。
- 页面外层背景色为 `@color-bg-page`，内容卡片保持 16px 外边距。

### 5.2 导航

- 侧边导航使用蓝色垂直菜单，选中项背景 `Primary Subtle`，图标白色，文字 14px。
- 顶部导航（若存在）采用白底 + 左侧 Logo + 右侧用户信息。

## 6. 图标与插图

- 图标统一使用 Ant Design Outline 风格，颜色采用主色或状态色。
- 统计卡片、通知等配合半透明圆形或图标背景块，加强视觉识别。
- 空态、成功提示可选用 Ant Design 自带插图，如 `Empty`、`Result` 组件。

## 7. 样式落地与实现

1. **变量文件**：在 `src/styles/variables.less` 或 `theme.less` 中定义上述颜色、字体、圆角变量，项目统一引用。
2. **组件重构顺序**：建议按照“控制面板 → 统计卡片 → 病历/文书列表 → 规则面板 → 其他页面”依次替换样式，确保不影响业务功能。
3. **样式书写约定**：所有局部样式使用 `scoped less + :deep` 配合 BEM 命名，避免冲突。
4. **响应式验证**：每次改动需在 1280px / 1024px / 768px / 375px 分辨率下检查布局。

## 8. 示例变量片段

```less
// colors.less
@color-primary: #0B64D4;
@color-primary-light: #1E88FF;
@color-primary-dark: #084C9E;
@color-primary-subtle: #E6F4FF;

@color-text-primary: #1F1F1F;
@color-text-secondary: #595959;
@color-text-tertiary: #8C8C8C;

@color-bg-page: #F5F7FB;
@color-bg-card: #FFFFFF;
@color-border: #E5E7EB;

@color-success: #52C41A;
@color-warning: #FAAD14;
@color-error: #F5222D;
@color-info: #2C8EAA;
```

---

此文档为初稿，后续可根据实际开发情况补充：导航栏、Tabs、Modal、Breadcrumb 等组件规范，以及图标库、插画风格等内容。请在界面改造时优先参照本规范执行，确保视觉与交互一致。
