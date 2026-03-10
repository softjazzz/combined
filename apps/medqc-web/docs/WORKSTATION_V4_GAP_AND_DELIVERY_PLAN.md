# Workstation V4 差距分析与交付计划

## 1. 文档目的

本文档用于汇总 `docs/PRD-泸县验收收尾.md` 与 `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` 的对比结果，并将分析结论落成可执行的开发计划。

文档范围限定为：

- PRD 中 M1-M8 的验收要求
- `WorkstationV4View.vue` 当前实现现状
- 仓库内已存在、可复用的组件
- 以 `M1 / M2 / M3-A / M4` 为优先的实施路径

## 最新完成度矩阵（2026-03-10）

说明：本矩阵反映当前代码实际落地状态，作为执行快照。若与后文“原始 GAP 分析”存在差异，以本矩阵为准。

### P0（验收关键闭环）

| 项目 | 状态 | 当前结果 | 关键文件 |
| --- | --- | --- | --- |
| M1 首页提取（SSE） | 已完成 | 支持流式提取、结果展示、预览联动 | `WorkstationV4View.vue` |
| M1.8 首页导出（3格式） | 已完成 | 已接通 `@export`，卫健委/医保/结算清单可下载 | `WorkstationV4View.vue`、`FrontPagePanel.vue` |
| 首页保存闭环 | 已完成 | 已接通 `@save` 到持久化接口 `PUT /api/medical-records/frontpage` | `WorkstationV4View.vue`、`backend/app/routers/medical_records.py` |
| M2 形式质控接入 | 已完成 | 已在悬浮分析面板接入质控结果展示与字段定位 | `WorkstationAssistPanel.vue`、`QCResultTab.vue` |
| M3-A 编码质控接入 | 已完成 | 已接后端编码质控检查，并支持编辑后刷新 | `QCResultTab.vue`、`useQcPipeline.ts` |
| M4 ICD 查询与回填 | 已完成 | 支持主/其他诊断、主/其他手术回填（含索引） | `WorkstationV4View.vue`、`ICDSearchPanel.vue` |
| 量化验收基线产物 | 已完成 | 已有脚本、数据模板、报告模板，可复现跑数 | `backend/scripts/run_frontpage_acceptance.py`、`backend/docs/frontpage_acceptance_dataset_template.json`、`backend/docs/FRONTPAGE_ACCEPTANCE_REPORT_TEMPLATE.md` |

### P1（工程收敛）

| 项目 | 状态 | 当前结果 | 关键文件 |
| --- | --- | --- | --- |
| 状态与类型抽离 | 已完成 | 已抽离 `useWorkstationSession/useFrontpageDraft/useQcPipeline/types` | `views/workstation-v2/composables/*`、`views/workstation-v2/types.ts` |
| 自动刷新编码质控 | 已完成 | ICD 回填与字段编辑后自动触发编码质控刷新 | `FrontPagePanel.vue`、`QCResultTab.vue`、`WorkstationV4View.vue` |
| 文书依据跳转 | 已完成 | 质控项支持“文书依据”跳转与片段展示 | `QCResultTab.vue`、`WorkstationV4View.vue` |
| 面板状态记忆 | 已完成 | 记忆面板显隐、Tab、ICD回填目标与索引等会话状态 | `useWorkstationSession.ts` |

### P2（演示项）

| 项目 | 状态 | 当前结果 | 关键文件 |
| --- | --- | --- | --- |
| DRG 优化建议闭环 | 已完成 | 已支持建议抽屉、采纳/忽略、重算流程 | `WorkstationV4View.vue`、`DRGGroupingTab.vue` |
| M5 消息概览 | 已完成（最小闭环） | 已在 V4 悬浮面板增加消息 Tab，支持未读筛选、已读、全部已读、去处理跳转病历 | `WorkstationAssistPanel.vue`、`WorkstationV4View.vue` |
| M3-B AI画像深化 | 部分完成 | 已接入画像面板，深度可视化（时间轴/3D）待增强 | `AIProfileDashboard.vue` |
| M6-M8 DRG 扩展分析 | 部分完成 | 已接入分组与优化建议，事前/事中/事后完整分析仍可继续扩展 | `DRGGroupingTab.vue`、`useDRGGrouping` |

## 2. 基线结论

### 2.1 V4 已实现部分

`WorkstationV4View.vue` 当前已覆盖以下能力：

- 列表模式：科室导航、病历卡片网格、搜索筛选
- 详情模式基础布局：患者信息区、文书预览区
- M1 首页自动生成主链路：SSE 流式提取、提取结果展示、首页预览
- 文书列表加载与 Drawer 预览

### 2.2 当前核心差距

当前问题不只是“缺少几个模块”，而是 `V4` 的详情页信息架构尚未与 PRD §7 对齐。

结合现有 UI 外壳和交互决策，本文档采用以下落地口径：

- 系统级页面外壳保留现状，不再强行重构整页为固定三栏
- `首页预览` 保留在主工作区，不放入悬浮面板
- `质控 / AI画像 / DRG` 统一收敛到一个悬浮分析面板，通过 Tab 切换
- 因此，本文档中的“对齐 PRD §7”采用“功能分区等价实现”而非“完全复制线框”

PRD 期望的结构是：

- 左侧：导航 / 病历入口
- 中间：病历内容与首页生成编辑区
- 右侧：质控 / 分析面板
- 右侧包含 4 个 Tab：
  - Tab1：质控结果
  - Tab2：首页预览
  - Tab3：AI画像
  - Tab4：DRG分组

当前 `V4` 实际提供的是：

- 左侧：患者信息与文书预览
- 右侧：首页生成主区
- 右侧仅有 2 个 Tab：
  - 提取结果
  - 首页预览

因此，当前最主要的问题不是系统外壳是否三栏，而是“详情工作区缺少统一分析面板能力”。本方案将其修正为：

- 主工作区负责：首页提取结果、字段编辑、首页预览、导出
- 悬浮分析面板负责：质控、AI画像、DRG

## 3. 更严谨的 GAP 清单

### 3.1 已实现

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 列表模式 | 已实现 | 已有科室导航、卡片网格、筛选 |
| 详情模式基础流转 | 已实现 | 已有患者信息、文书预览、首页生成区 |
| M1 首页自动提取 | 已实现 | 已接入 SSE 提取与预览 |
| 文书预览 | 已实现 | 已支持 Drawer 预览 |

### 3.2 未集成到 V4

| PRD 模块 | V4 状态 | 优先级 | 说明 |
| --- | --- | --- | --- |
| §7 工作站分析区 | 未按 PRD 形态落地 | P0 | 改为“主工作区 + 统一悬浮分析面板”的等价实现 |
| M2 形式质控 | 系统已有能力，V4 未集成 | P0 | `QCAlertPanel` 已有质控链路，但当前为浮动面板 |
| M3-A 编码质控 | 系统已有能力，V4 未集成 | P0 | `QCAlertPanel` 已接后端编码质控接口，但 V4 未内嵌 |
| M4 ICD 智能查询 | 系统已有能力，V4 未集成入口 | P0 | `V2` 已有 ICD 查询页，V4 缺少入口与回填联动 |
| M1.8 首页导出入口 | 未明确集成 | P0 | V4 内需要完整导出链路 |
| M3-B 画像/时间轴 | 未集成 | P2 | 演示项 |
| M5 消息概览 | 未集成 | P2 | 演示项 |
| M6 DRG 事前 | 未集成 | P2 | 演示项 |
| M7 DRG 事中 | 未集成 | P2 | 演示项 |
| M8 DRG 事后 | 未集成 | P2 | 演示项 |

### 3.3 已有但尚未在 V4 使用的组件

| 组件 | 当前状态 | 建议用途 |
| --- | --- | --- |
| `QCAlertPanel.vue` | 组件已存在，V4 未导入，且当前为浮动面板 | 可扩展为统一悬浮分析面板的基础组件 |
| `ICDSearchPanel.vue` | 组件已存在，V4 未导入，但 V2 已集成 | 用于 M4 ICD 查询入口与回填 |
| `ICDDetailPanel.vue` | 组件已存在，V4 未导入 | 用于 ICD 详情展示 |
| `DraftListSidebar.vue` | 组件已存在，V4 未导入 | 可选增强，不属于必验项 |

### 3.4 需在项目层面进一步确认的点

以下内容更准确的表述应当是“在 V4 中未体现”，不能仅凭 `WorkstationV4View.vue` 单文件直接判定“系统不存在”：

- M1.8 三种格式导出能力
- M5 消息概览能力
- DRG 相关页面或后端能力

## 4. 交付策略

### 4.1 目标

以最短路径达到验收要求，优先完成以下闭环：

1. 先将 `V4` 详情页结构调整为 PRD §7 三栏布局
2. 先补齐必验项：
   - M1 首页自动生成
   - M2 形式质控
   - M3-A 编码质控
   - M4 ICD 智能查询
3. 补齐导出能力，形成完整首页链路
4. 最后补齐演示项

调整为更贴合现状的实现方式后，目标落地为：

1. 保留当前系统级外壳与工作区主结构
2. 首页提取、编辑、预览、导出仍留在主工作区
3. 新增统一悬浮分析面板，承载：
   - 质控
   - AI画像
   - DRG
4. ICD 查询作为字段级辅助能力接入主工作区

### 4.2 优先级定义

#### P0

- 工作区主结构调整与主预览区收敛
- `QCAlertPanel` 升级为统一悬浮分析面板
- M2 / M3-A 质控能力接入与规则验证
- M4 ICD 查询入口与回填联动
- M1.8 首页导出接入

#### P1

- 状态管理收敛
- 接口契约梳理
- 跨面板交互联动
- 文书溯源 / 可解释性增强

#### P2

- AI画像 / 时间轴
- DRG 分组与分析面板
- 消息概览

## 5. 实际开发排期

### 5.1 排期假设

- 以前端 1 人为主开发，后端协同支持为基准
- 1 人日按 6-7 小时有效开发估算
- 第一目标是形成“可验收版本”，不是第一轮就做到架构最优

### 5.2 第一阶段：验收关键闭环

预计工期：约 7 人日

| 任务 | 工期 | 负责人 | 交付结果 |
| --- | --- | --- | --- |
| 工作区主结构调整 | 1-1.5 人日 | 前端 | 保留主工作区承载提取、编辑、预览、导出 |
| 统一悬浮分析面板改造 | 1-1.5 人日 | 前端 | 基于 `QCAlertPanel` 扩展为 `质控 / AI画像 / DRG` 多 Tab 面板 |
| M2 / M3-A 质控能力接入 | 1 人日 | 前端 + 后端 | 复用现有质控链路，在 V4 中实现内嵌展示与定位 |
| 规则覆盖与质量补齐 | 0.5-1 人日 | 前端 + 后端 | 验证形式质控 / 内涵质控规则数量与效果 |
| M4 ICD 查询接入 | 0.5 人日 | 前端 | 复用现有 ICD 查询能力，为 V4 增加入口和回填 |
| M1.8 首页导出接入 | 1 人日 | 前端 + 后端 | 三种导出入口与下载流程 |
| 量化验收指标验证 | 1 人日 | 前端 + 后端 | 基于固定测试集验证 PRD §5 指标并输出基线报告 |

阶段目标闭环：

- 选择病历
- 启动 AI 提取
- 查看首页草稿
- 执行形式质控
- 执行编码质控
- 使用 ICD 查询辅助修正
- 查看首页预览
- 导出首页
- 基于固定测试集输出量化验收结果

### 5.3 第二阶段：稳定性与工程收敛

预计工期：2.5-4 人日

| 任务 | 工期 | 负责人 | 交付结果 |
| --- | --- | --- | --- |
| 工作站状态管理收敛 | 1-1.5 人日 | 前端 | 抽离 composable/store |
| 接口契约梳理 | 0.5-1 人日 | 前后端协同 | 减少页面层字段转换 |
| 跨面板交互联动 | 0.5-1 人日 | 前端 | 点击定位、自动刷新、预览同步 |
| 文书溯源增强 | 0.5 人日 | 前后端协同 | 字段来源提示与依据展示 |

### 5.4 第三阶段：演示项补齐

预计工期：2-3.5 人日

| 任务 | 工期 | 负责人 | 交付结果 |
| --- | --- | --- | --- |
| AI画像 / 时间轴 | 0.5-1 人日 | 前端 | Tab3 演示内容 |
| DRG 面板接入 | 1-1.5 人日 | 前端 + 后端 | Tab4 DRG 结果展示 |
| 消息概览接入 | 0.5-1 人日 | 前端 | 工作站内消息摘要入口 |

### 5.5 测试与验收准备

预计工期：1.5-2 人日

| 任务 | 工期 | 交付结果 |
| --- | --- | --- |
| 前端冒烟测试 | 0.5 人日 | 页面主路径稳定 |
| 接口联调测试 | 0.5-1 人日 | SSE / 质控 / ICD / 导出链路通过 |
| 验收脚本整理 | 0.5 人日 | 可复现的演示路径 |

### 5.6 总体工期估算

| 版本目标 | 工期 | 范围 |
| --- | --- | --- |
| 最小可验收版本 | 约 7 人日 | 仅 P0 |
| 稳定版本 | 7.5-11 人日 | P0 + P1 |
| 演示完整版 | 9.5-14.5 人日 | P0 + P1 + P2 |

## 6. 按文件拆解的开发任务表

本节按文件粒度拆解任务，便于直接派工。

### 6.1 前端核心文件

| 文件 | 任务 | 优先级 | 说明 |
| --- | --- | --- | --- |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 调整详情工作区结构 | P0 | 主工作区负责提取、编辑、预览、导出 |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 保留或增强首页预览区域 | P0 | `首页预览` 不进入悬浮分析面板 |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 接入统一悬浮分析面板入口 | P0 | 用于打开 `质控 / AI画像 / DRG` |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 接入 `ICDSearchPanel` 入口与可选 `ICDDetailPanel` | P0 | M4，重点是入口和回填 |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 增加首页导出操作 | P0 | M1.8 |
| `apps/medqc-web/src/views/workstation-v2/WorkstationV4View.vue` | 增加 AI画像 与 DRG 的触发入口 | P2 | 演示项，由悬浮分析面板承载 |

### 6.2 现有可复用组件

| 文件 | 任务 | 优先级 | 说明 |
| --- | --- | --- | --- |
| `apps/medqc-web/src/views/workstation-v2/components/QCAlertPanel.vue` | 扩展为统一悬浮分析面板基础组件 | P0 | 保留浮动态，增加多 Tab 承载 `质控 / AI画像 / DRG` |
| `apps/medqc-web/src/views/workstation-v2/components/ICDSearchPanel.vue` | 复用现有搜索能力，补 V4 入口和选择回调 | P0 | 需支持回填当前诊断/手术项 |
| `apps/medqc-web/src/views/workstation-v2/components/ICDDetailPanel.vue` | 核对详情展开方式 | P1 | 第一轮可选 |
| `apps/medqc-web/src/views/workstation-v2/components/DraftListSidebar.vue` | 评估是否需要纳入 V4 | P2 | 非必验项 |
| `apps/medqc-web/src/views/workstation/FrontPagePanel.vue` | 增加字段聚焦 / 高亮能力 | P1 | 供质控结果定位字段 |
| `apps/medqc-web/src/components/frontpage/HmFrontpagePreview.vue` | 增加导出入口或暴露工具栏插槽 | P0 | 首页导出集成点 |

### 6.3 建议新增或拆分的前端文件

为避免 `WorkstationV4View.vue` 继续膨胀，建议补充或拆分以下文件：

| 新文件 | 任务 | 优先级 | 说明 |
| --- | --- | --- | --- |
| `apps/medqc-web/src/views/workstation-v2/components/WorkstationAssistPanel.vue` | 统一悬浮分析面板 | P0 | Tab 承载 `质控 / AI画像 / DRG` |
| `apps/medqc-web/src/views/workstation-v2/composables/useWorkstationSession.ts` | 管理当前患者、文书状态、模式切换 | P1 | 收敛页面级状态 |
| `apps/medqc-web/src/views/workstation-v2/composables/useFrontpageDraft.ts` | 管理提取状态、草稿状态、预览同步 | P1 | 抽离 M1 状态逻辑 |
| `apps/medqc-web/src/views/workstation-v2/composables/useQcPipeline.ts` | 管理形式质控与编码质控请求和结果 | P1 | 避免页面内堆积流程控制 |
| `apps/medqc-web/src/views/workstation-v2/types/workstation.ts` | 统一工作站相关 TS 类型定义 | P1 | 降低隐式结构风险 |

### 6.4 前端 API 层任务

具体文件名需要按当前项目 API 模块实际结构落位。

| 模块 | 任务 | 优先级 | 说明 |
| --- | --- | --- | --- |
| 首页 API 模块 | 暴露提取、预览、导出能力 | P0 | 复用现有 SSE 接口 |
| 质控 API 模块 | 复用现有质控接口与编码质控接口 | P0 | 核心工作是统一前端消费结构与结果定位 |
| ICD API 模块 | 复用现有搜索与详情接口 | P0 | 重点不是新建接口，而是入口与回填联动 |
| DRG API 模块 | 暴露分组 / 预测接口 | P2 | 演示项 |

### 6.5 后端配套任务

如果前端无法直接复用现有接口，需要后端补齐以下内容：

| 后端模块 | 任务 | 优先级 | 说明 |
| --- | --- | --- | --- |
| 形式质控接口 | 确认首页草稿入参与返回结构 | P0 | 前端已有 `integratedQCEngine`，重点是验收覆盖和结果质量 |
| 编码质控接口 | 确认诊断 / 手术入参结构 | P0 | V4 需复用 `/api/v1/qc/coding-qc/check` |
| ICD 查询接口 | 确认关键字查询与候选结构 | P0 | 现有接口已可用，重点是保证 V4 可直接回填 |
| 导出接口 | 确认三种导出模式与下载响应 | P0 | 验收关键项 |
| DRG 接口 | 确认分组结果与解释字段 | P2 | 演示项 |
| 量化验收测试集 | 准备固定样本并输出指标报告 | P0 | 验证 PRD §5 的时效、准确率、规则数指标 |

### 6.6 交互联动任务

| 交互 | 涉及文件 | 优先级 | 说明 |
| --- | --- | --- | --- |
| 点击质控项定位字段 | `WorkstationV4View.vue`、`FrontPagePanel.vue`、`QCAlertPanel.vue` 或 `WorkstationAssistPanel.vue` | P1 | 支持滚动与高亮 |
| 选择 ICD 候选回填诊断 / 手术 | `WorkstationV4View.vue`、`ICDSearchPanel.vue` | P0 | 验收可见能力 |
| 编辑诊断后刷新编码质控 | `useQcPipeline.ts`、`WorkstationV4View.vue` | P1 | 避免结果过期 |
| 草稿更新后同步预览 | `useFrontpageDraft.ts`、`HmFrontpagePreview.vue` | P1 | 保证预览可信 |
| 文书依据跳转 | `WorkstationV4View.vue` 与文书预览区 | P1 | 提升可解释性 |
| 悬浮分析面板记忆上次 Tab / 展开状态 | `WorkstationAssistPanel.vue` 或 `QCAlertPanel.vue` | P1 | 保持连续操作体验 |

## 7. 推荐实施顺序

1. 先调整 `WorkstationV4View.vue` 主工作区结构
2. 保留首页预览在主工作区，不放入悬浮面板
3. 改造 `QCAlertPanel` 或新增 `WorkstationAssistPanel`，形成统一悬浮分析面板
4. 在悬浮分析面板中闭环 M2 与 M3-A
5. 接入 `ICDSearchPanel` 的入口与回填，闭环 M4
6. 在首页预览区补齐导出能力，闭环 M1.8
7. 基于固定测试集跑量化验收
8. 抽离 composable，收敛状态管理
9. 最后补 AI画像 与 DRG 面板

## 8. 验收清单

### 8.1 必验项

- M1 首页自动生成可在 V4 内完整运行
- M2 形式质控可在 V4 内查看并定位问题
- M3-A 编码质控可在 V4 内查看并辅助修正
- M4 ICD 查询可在 V4 内发起并回填结果
- M1.8 首页导出可从 V4 直接触发
- 首页预览保留在主工作区，支持导出前确认

### 8.2 量化验收指标

需在第一阶段末尾使用固定测试集进行验证，并输出基线报告。建议纳入以下指标：

- 首页生成时效：P95 <= 30 秒
- 字段填充率：均值 >= 90%
- 诊断提取准确率：均值 >= 90%
- 编码建议首条命中率：均值 >= 85%
- 形式质控规则数：>= 80 条
- 内涵质控规则数：>= 80 条
- 质控检查速度：P95 < 1 秒
- ICD 搜索响应：P95 < 500ms

### 8.3 推荐演示路径

1. 选择一份病历
2. 进入详情模式
3. 启动 AI 首页提取
4. 查看提取结果与首页预览
5. 打开悬浮分析面板，展示形式质控问题
6. 切换到编码质控结果
7. 使用 ICD 查询修正一条诊断
8. 再次执行质控，展示问题减少
9. 导出首页
10. 切换到 AI画像或 DRG Tab 作为扩展演示

## 9. 实施决策建议

如果目标是最短路径达到验收要求，建议执行策略如下：

- 不要先做 AI画像 或 DRG
- 不要先做外观优化或可选组件美化
- 先把主工作区改顺，保留首页预览在主区
- 先完成统一悬浮分析面板改造
- 按顺序补齐 `M2 / M3-A -> M4 -> M1.8`
- 第一阶段结束前补做量化验收验证

这是从当前 `V4` 到 PRD 验收通过的最短实施路径。
