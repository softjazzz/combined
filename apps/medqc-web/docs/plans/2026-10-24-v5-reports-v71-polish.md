# V5报表与整改五页 V7.1 收尾

## 范围

日期2026-10-24，基线 `79ae7d43a`，工作树 `C:/medqc-pr8-adapt`、分支 `codex/pr8-business-report-adapt-20261023`。只做展示层：V7.1视觉一致性、信息层级、响应式与可访问性。不改API、引擎、规则、评分、授权、数据库或迁移；不扩展80项台账。

| 提交        | 页面 / 子面板                                       |
| ----------- | --------------------------------------------------- |
| `7b69a7597` | 特殊病历报表、配置抽屉、图表                        |
| `b62811e97` | 质控员工作分析、人工质控页签                        |
| `3224fd20f` | 核心制度面板；病历质量/病案首页跨页对齐             |
| `e4e4446b8` | 五页及抽屉/弹窗的加载、空、错误、未知状态与弹层层级 |

## 设计

- 页头统一 `mq-page`/`mq-page-head`，眉标“统计分析 · 质量报表”；页内一级切换由 `a-tabs`/`a-segmented` 改为 `mq-segmented`。报表级切换用 `tablist/tab/aria-selected`（与病历质量一致），视图或筛选切换用 `group/aria-pressed`。
- 按钮统一原生 `mq-btn` + `MqIcon`，五页及子面板不再引用 Lucide；表格 `mq-table`，数字列右对齐等宽；指标数值统一34px中性色。
- 状态胶囊只映射真实状态：已核验/未知/未派发及计数0保持中性；分类未知、待处理为warning，不可用、驳回为danger，通过为success，命中/待验收为info。
- 复杂口径用原生 `details` 折叠，正文完整保留；“八类可重叠、缺失来源单列未知、未核验归档”“人工缺陷未纳入、多制度可重叠”“缺少完整缺陷明细、总数未知”等业务限制始终可见。
- 状态规则：加载 `role=status` 三级文字；错误 `role=alert` + danger Token + issue图标；不可用/未知用warning Token；空态居中三级文字。整改主链刷新保留 `a-spin`（列表留在原位），错误由 `a-alert` 改为同视觉的局部 `.state-error`。
- 弹层：报表抽屉统一1100（人工质控明细、特殊病历配置由默认1000补齐），派发Modal 1200，整改Drawer 1300。配置抽屉的tags Select改挂局部 `popupContainer`，避免落回body的1050层被遮挡。
- 私有样式在 `styles/` 局部文件；未改 `reportPage.css`、Token、`mq-components.css`、主题或任何18个保护文件。`StaffAnalysisView.vue` 由1113行降至约840行。

## 保护

保留全部 `data-testid`、权限可见性、筛选、排名、下钻、分页、CSV导出；请求代次、迟到响应丢弃、版本漂移拒绝、冻结快照导出、CAS保存与写后回读逻辑未改。未发起任何数据库写入。

## 验收

- 基线：本批6组13文件154项通过，`vue-tsc`、只读ESLint通过。
- 结果：同组157项通过（新增3项展示/弹层断言，各页另补展示断言）。断言调整仅限结构变化：页签改点分段按钮、导出按钮改名“导出 CSV”、未知分类确认缺陷按指标卡取值、人工口径由 `a-alert` 改查 `details`；功能断言未删。全量 `vue-tsc`、全 `src` 只读ESLint、每次暂存文件的precommit/编码/密钥检查通过。未运行全仓 `test:unit`。
- 浏览器（内置面板，`admin@medqc.com`）：1440/1180/390 下特殊病历、质控员/人工质控、病历质量核心制度页签、整改待办均无页面横向溢出；按钮38px且图文同排；筛选网格不拉伸末行；390下分段单行等分；特殊病历配置抽屉错误态正常。

## 隔离持久账号数据态补验

2026-10-24，基于 `e4e4446b8` 补验。前端 `localhost:3011`、隔离后端 `127.0.0.1:8011` 均来自当前工作树。通过既有私有运行器的只读连接核对 `current_database()` 为 `medqc_pr8_reports_acceptance_20261023_2aefa0`，`transaction_read_only=on`。浏览器正常登录既有持久质控账号，分别读取运行、终末机构的授权范围；未使用演示账号或替换浏览器令牌。

这里的“真实数据态”指隔离 PostgreSQL 已持久化的合成验收数据，不是医院真实患者验收。本轮未新增种子、未执行迁移、未再次派发/提交/审核整改、未保存机构配置；不写业务库、不推送、不合并。

| 页面/子面板 | 浏览器实测及结果 |
| --- | --- |
| 病历质量分析 | 终末范围3份、完成2份、平均97.50、确认自动缺陷1条；科室下钻返回2份已完成结果，分别95/甲、100/甲。运行范围8份、完成2份、平均99.00、自动缺陷1、人工缺陷2，科室下钻正常。范围病例数与已保存结果明细的分母不同，不把未完成病例伪造成已有结果。 |
| 整改分析 | 运行、终末各有“催办已整改”1条；运行的2条非本轮人工来源单列未知，不硬归七标签。打开当前自动缺陷历史，可见派发、催办、撤回、提交、驳回、再次催办、再次提交、验收共8个事件及关联ID。原确认缺陷与评分未因整改通过而清零。 |
| 核心制度 | 终末结果2份可读、1份不可用；2份分类未知，确认缺陷1。病例详情返回冻结结果ID与规则明细，制度原文抽屉可打开；未伪造制度合规率。已分类正例仍缺数据，见下方边界。 |
| 特殊病历报表 | 机构版本1正常读取；死亡已知命中1、来源未知2。专用标准版本1，命中病例98/乙，历史分保持未知；科室、等级、缺陷三路下钻均返回该病例。图表/明细切换正常，三张图均实际绘制；未知来源下钻计2例。配置抽屉读取Y/N及L1–L4，下拉挂载于抽屉内部可见，未保存。 |
| 病案首页统计 | 终末授权范围1份病案、45条非编码缺陷（警告31、错误14）；FQ-001规则与科室下钻返回同一病例、45条缺陷；编码无结果不冒充已质控。 |
| 质控员工作分析/人工报表 | 终末人员催办2条可下钻；运行人员初审病历4份可下钻为4条事件。人工报表8条，审核通过8、整改验收通过1、未派发7；明细显示冻结来源及当前审核/整改独立状态。录入人筛选后4条，与实际列表一致。 |
| 整改待办/弹窗 | 运行已通过列表3条，选择浏览器验收任务可读8事件及指定第二次提交的正文比较，空正文明确不可比较。由整改分析进入派发弹窗，真实缺陷可选、医生菜单两名候选可见且能选中；DOM确认下拉在Modal内部。取消草稿，不重复派发。 |

### 实测修复

1. 人工报表有长表格时，根网格隐式auto列被最小内容宽度撑至1481.5px，390视口内筛选区被裁切；仅在私有CSS明确 `grid-template-columns: minmax(0, 1fr)`。原浏览器失败断言修复后通过，筛选宽度257.2px，主内容 `scrollWidth=clientWidth=289`，长表格保留内部滚动。
2. 首页统计390视口下，标题与来源切换同行导致标题逐字换行、来源切换越界36px；只在该页面局部480断点上下排列，修复后原断言通过，不改共享 `reportPage.css` 或公共分段组件。

新增两条聚焦样式结构回归；JSDOM不能证明实际布局，以上尺寸通过原内置浏览器只读DOM断言及截图核实。1440桌面与390窄屏覆盖非空图表、病例抽屉、人工报表和整改比较；1180补验特殊报表。未声称所有页面/所有状态均在三个宽度穷举通过。

相关回归最终为19文件204项通过（本轮修复前202项）；包含报表组件、6组API、导出竞态、整改弹窗/待办、V5路由及18个V7.1保护文件。保护基线仍为 `754fa2f7af23e9d60209f3cbbcf96e3d59d9813f`，共享保护文件内容未改。未跑全仓 `test:unit`，不把聚焦套件计作全量回归。

最终全量 `pnpm run type-check`、全 `src` 只读ESLint、暂存5个文本文件的编码检查及 `git diff --check` 均通过。过程中新增测试的 `get().exists()` 类型错误已改成 `find().exists()` 后重跑，不绕过类型检查。

```powershell
corepack pnpm exec vitest run src/views/qc/reports/__tests__ src/api/__tests__/qualityReports.spec.ts src/api/__tests__/frontpageQualityReport.spec.ts src/api/__tests__/specialRecordReports.spec.ts src/api/__tests__/staffAnalysis.spec.ts src/api/__tests__/manualQualityReport.spec.ts src/api/__tests__/coreSystemReports.spec.ts tests/unit/components/qc/CaseRectificationCreate.spec.ts tests/unit/views/workstation/HomeRectificationTodos.spec.ts tests/unit/router/workstation-report-protection.spec.ts tests/unit/router/workstation-report-adaptation.spec.ts
```

### 证据位置

已落盘到本机忽略目录 `.tmp/0910-full-audit/`，均为 `-private.png`，不提交合成病历截图：

- `pr8-v71-data-quality-drill-private.png`、`pr8-v71-data-quality-drill-narrow-private.png`
- `pr8-v71-data-core-detail-private.png`
- `pr8-v71-data-special-charts-private.png`、`pr8-v71-data-special-menu-private.png`、`pr8-v71-data-special-narrow-private.png`
- `pr8-v71-data-frontpage-rule-private.png`、`pr8-v71-data-frontpage-narrow-fixed-private.png`
- `pr8-v71-data-staff-events-private.png`、`pr8-v71-data-staff-narrow-private.png`
- `pr8-v71-data-manual-detail-private.png`、`pr8-v71-data-manual-narrow-fixed-private.png`
- `pr8-v71-data-feedback-history-private.png`、`pr8-v71-data-feedback-narrow-private.png`、`pr8-v71-data-rectification-menu-private.png`

## 仍有边界

- 核心制度缺少已分类的冻结结果，已验“分类未知/不可用/明细”，未验“已分类制度排行正例”；不修改读取规则或造分类补绿。
- 本轮不重做配置写入、整改写操作全链及权限反例；此前专项记录不等同于本轮重跑。各CSV按钮保留既有回归，但本轮不声称全部下载已浏览器验收。
- `mq-segmented__item` 公共高度32px，低于36px触控建议；属保护文件，未改。
- 特殊病历按钮文案“下载报表/下载病例”与其他页“导出 CSV”不一致，属现有业务文案，保留。
