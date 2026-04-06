# Workstation V4 医疗浅色 DESIGN.md

> 适用范围：`workstation-v4`（主列表页）与 `QCOverviewView`（首页概览页）  
> 基线来源：参考 Vercel 风格 DESIGN.md 的结构化写法，结合当前业务页面落地  
> 版本：v1.0（2026-04-06）

## 1. Visual Theme & Atmosphere

- 设计关键词：医疗专业、浅色清洁、信息密度高但层级清晰
- 风格目标：保留中后台效率感，不做营销化视觉
- 视觉结构：固定三层
  - 第 1 层：KPI 指标行（4 卡）
  - 第 2 层：趋势/排行双栏分析区
  - 第 3 层：明细列表区（状态筛选 + 任务列表/批量表格）
- 主题约束：仅浅色主题，不启用深色背景或深色头图

## 2. Color Palette & Roles

| 语义角色  | 色值                     | 用法             |
| --------- | ------------------------ | ---------------- |
| 主背景    | `#f8fafc` ~ `#edf2f7`    | 页面画布渐变背景 |
| 主文字    | `#0f172a`                | 标题、关键数据   |
| 次文字    | `#475569` / `#5b6b84`    | 正文、说明       |
| 弱文字    | `#64748b` / `#94a3b8`    | 辅助信息、占位   |
| 品牌主色  | `#2f6fed` / `#1e5ae0`    | 主按钮、强调态   |
| 品牌浅底  | `rgba(239,246,255,0.96)` | 选中态、强调背景 |
| 高风险    | `#ef4444`                | 风险高优提示     |
| 进行中    | `#2563eb`                | 流程进行中状态   |
| 超时/警告 | `#f59e0b`                | 超时、预警       |
| 成功/通过 | `#10b981`                | 通过率、完成态   |
| 分割/边框 | `rgba(226,232,240,0.88)` | 卡片边界、分隔   |

## 3. Typography Rules

- 字体优先级：系统中文字体栈 + 西文无衬线（保持后台可读性）
- 字重约束：
  - `700`：页面标题、KPI 主数值
  - `600`：区块标题、交互标签
  - `400/500`：正文、辅助说明
- 建议字号层级：
  - 页面主标题：`28px`
  - 区块标题：`17px` / `14px`
  - KPI 数值：`34px`
  - 正文：`13px-14px`
  - 辅助：`11px-12px`

## 4. Component Stylings

### 4.1 顶部 Analysis 总览区

- 容器：圆角 `24px`，浅蓝到白渐变背景，轻阴影
- 右上角统一操作：`查询/重置/刷新`
- 操作按钮统一胶囊圆角（`999px`）

### 4.2 KPI 指标卡（4 卡）

- 每卡圆角 `18px`，白底 + 轻边框 + 轻阴影
- 结构：`label / value / desc`
- 状态边框色区分：
  - `brand`：总量
  - `danger`：高风险
  - `warning`：处理中
  - `success`：完成率/通过率

### 4.3 趋势/排行双栏卡

- 左栏：Tabs + 进度条（阶段分布、流程负载）
- 右栏：列表排行（科室、风险原因、优先级）
- 卡片外观：圆角 `20px`，白底，弱边框

### 4.4 列表区

- 容器：圆角 `24px`，白底，轻阴影
- 头部：标题 + 副标题（总条数）
- 状态筛选条放入列表区头部下方，避免入口分散

## 5. Layout Principles

- 最大内容宽度：`1440px`
- 主内容横向间距：`px-4 xl:px-5`
- 常规区块间距：`12px / 16px / 20px / 24px`
- 栅格规则：
  - KPI：`4 列`（桌面）→ `2 列`（中屏）→ `1 列`（移动）
  - 分析区：`1.3fr / 1fr`（桌面）→ `1 列`（中小屏）

## 6. Depth & Elevation

- 主策略：浅层级、弱投影、避免重拟物
- 面板级阴影：
  - `0 14px 34px rgba(148,163,184,0.12~0.16)`
- 卡片级阴影：
  - `0 10px 24px rgba(148,163,184,0.12)`
- 输入框与交互态阴影：
  - 使用品牌浅色 `brand-shadow`，仅在 hover/focus 增强

## 7. Do's and Don'ts

### Do

- 统一在区块右上角放置查询相关操作
- 指标与状态使用语义色，不做装饰性渐变
- 保持数据源不变，仅做前端聚合展示
- 复杂信息先分层再展开（总览 → 分析 → 明细）

### Don't

- 不新增后端接口或修改请求/响应契约
- 不引入新的图表依赖（优先 `a-progress` + 列表）
- 不使用深色头图或高饱和背景
- 不打散现有事件流（打开病历、批量处理、路由同步）

## 8. Responsive Behavior

- `<=1279px`
  - KPI 由 4 列降为 2 列
  - 趋势/排行由双栏改单栏
- `<=1023px`
  - KPI 改 1 列
  - 顶部操作区换行
  - 搜索与筛选控件改纵向堆叠
- 移动端触控目标建议：`>=36px` 高度

## 9. Agent Prompt Guide

### 快速约束（给 AI 的一句话）

“请按 WorkstationV4 医疗浅色 DESIGN.md 生成页面：三层结构（KPI/分析/明细），浅色卡片风格，不改数据接口与业务流程。”

### 可复用 Prompt 模板

1. “创建一个医疗质控工作台总览区：浅蓝-白渐变容器，左侧标题与副标题，右侧胶囊按钮（查询/重置/刷新）。”
2. “生成 4 张 KPI 卡：总量/高风险/处理中/通过率，白底轻阴影，数值 34px，状态边框色区分。”
3. “生成 Analysis 双栏：左栏 tabs+progress 展示阶段分布与流程负载，右栏用 TopN 列表展示科室与风险原因排行。”
4. “生成明细列表容器：标题、状态筛选条、任务列表，保持浅色中后台风格，避免深色主题。”

---

## 附录 A：CSS Token 清单（与现有实现对齐）

```css
:root {
  --workstation-bg-page: #f4f6f8;
  --workstation-bg-card: #ffffff;
  --workstation-text-primary: #0f172a;
  --workstation-text-secondary: #5b6b84;
  --workstation-text-muted: #94a3b8;

  --workstation-brand-500: #2f6fed;
  --workstation-brand-600: #1e5ae0;
  --workstation-brand-100: rgba(239, 246, 255, 0.96);
  --workstation-brand-border: rgba(191, 219, 254, 0.96);
  --workstation-brand-shadow: rgba(191, 219, 254, 0.24);

  --workstation-analysis-bg: linear-gradient(
    135deg,
    rgba(239, 246, 255, 0.95),
    rgba(255, 255, 255, 0.98)
  );
  --workstation-analysis-border: rgba(191, 219, 254, 0.8);
  --workstation-analysis-shadow: 0 14px 34px rgba(148, 163, 184, 0.16);

  --workstation-space-2: 8px;
  --workstation-space-3: 12px;
  --workstation-space-4: 16px;
  --workstation-space-5: 20px;
  --workstation-space-6: 24px;
}
```

## 附录 B：当前落地文件映射

- `apps/medqc-web/src/views/workstation-v4/components/WorkstationV4ListView.vue`
- `apps/medqc-web/src/views/workstation/QCOverviewView.vue`
- `apps/medqc-web/src/views/workstation-v4/styles/workstation-v4-view.css`
- `apps/medqc-web/src/views/workstation/components/HomeHeroBar.vue`
