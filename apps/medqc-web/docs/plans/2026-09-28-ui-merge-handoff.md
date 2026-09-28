# 工作台 UI 整改 · 合并到 `codex/lx0609-tech-debt-20260730` 交接文档

> 交接日期：2026-09-28
> 源分支：`codex/lx0609-rule-id-integration`（worktree：`C:\Users\Coldplay\.codex\worktrees\lx0609-rule-id-integration\LX888`；本地领先 `github/codex/lx0609-rule-id-integration`，**未推送**）
> 目标分支：`codex/lx0609-tech-debt-20260730`（检出在主工作区 `D:\LLM\LX888`；本地 `cf698bafe` 比 `github/` 上的 `4c835f9b0` 多 1 个未推送提交）
> UI 提交范围：`03ffd81af^..82c6f99fb`（52 个提交）
> 上一份交接（v7.1 迁移本身）：[2026-09-27-ui-v71-handoff.md](2026-09-27-ui-v71-handoff.md) ｜ 设计规范：[WorkstationV4-医疗浅色-DESIGN.md](../0418/UI/WorkstationV4-医疗浅色-DESIGN.md)

> **2026-09-28 更新：第一轮已由目标分支合并提交 `29c9ead09` 带入（到 `e1a003b7c` 为止）。本次只需做第 7 节的「第二轮增量合并」，第 0–6 节为第一轮记录。**

## 0. 先读这四条

1. **两条分支非常接近，合并很简单。** 分叉点是 `3dff664b4`（2026-09-27「记录发布范围复审通过及验收边界」）。源分支领先 55 个提交（52 个 UI + `c10d2c745` AGENTS 路径修正 + 2 个交接文档提交），目标分支领先 4 个提交。`git merge-tree` 试合并**只有 2 个冲突，都是文档**：`apps/medqc-web/AGENTS.md`、`apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md`；没有任何代码冲突。
2. **UI 整改只改了展示层。** 150 个文件：`src/views` 117、`src/components` 14、`tests` 8、`src/styles` 4、`docs` 4、`tailwind.config.js` / `src/main.ts` / `src/App.vue` 各 1；**没有改** `src/api`、`src/stores`、`src/services`、`src/router`、`src/types`、`src/domain` 和后端，也没有改业务流程、筛选项或接口契约。
3. **目标分支所在的主工作区 `D:\LLM\LX888` 有别人未提交的改动**（4 个修改、2 个已暂存又修改、97 个未跟踪）。2026-09-28 复核：源分支新增提交 `b5f10635f`（质控结果右侧栏阅读优化）后，合并带入的文件与主工作区未提交文件**有 1 个重叠**：`apps/medqc-web/tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`（主工作区对它有未提交修改）。快进时 git 会因「会覆盖本地修改」拒绝，这是安全拒绝，不会丢改动；此时需由用户决定先提交或另行处理主工作区的这份修改，**不要替用户 stash、reset 或 checkout**。另外主工作区还修改了 `CustomerQcResultDetailCard.vue`，本次合并不涉及该文件。因为存在已暂存改动，**不要直接在 `D:\LLM\LX888` 里做非快进合并**，也不要 stash / reset / checkout 那里的文件——按第 3 节在干净工作树里合并，再让主工作区快进。
4. 推送、删除分支或工作树需要用户明确授权；按路径暂存；提交信息用中文。

## 1. UI 整改内容

### 1.1 设计基础（v7.1 液态玻璃，纯蓝）

- Token：`src/styles/tokens-v2.css`（`--mq-*`），公共组件样式 `src/styles/mq-components.css`，均在 `src/main.ts` 全局加载；品牌蓝统一为 `#0A6CFF`（App.vue antd 主题、tailwind、index.css、design-tokens.less 已同步），**不用紫色**，红/橙/绿只表达状态。
- 定制双色图标：`src/components/icons/MqIcon.vue`、`MqIconTile.vue`、`mqIcons.ts`。
- 导航配置抽成纯函数：`src/components/layout/workstationNav.ts`（`findActiveNav` / `filterVisibleNav` / `resolveBreadcrumb`），规则 4 个子项、DRG/DIP 5 个子项各合并为一个入口，页内分段切换。
- 页面标题统一 `--mq-font-title: 32px`（原 40px；Windows 下中文走微软雅黑，只有常规/粗体两档，40px 粗体过重）。

### 1.2 按页面

| 模块 | 结果 |
| --- | --- |
| 外壳 / 侧栏 `WorkstationLayout.vue` | 去掉顶栏，账号区移入侧栏底部；分组可折叠（记在 `localStorage` 的 `mq-sider-closed-groups`，当前页所在分组自动展开）；分组标题 12px 浅灰标签、菜单 14px；图标去灰色底块，选中为淡蓝底；滚动条与折叠箭头按需出现；1440×900 全展开可见「系统配置」 |
| 登录页 | 保留毛笔字标语、医院标识、左文右卡；背景加蓝色光斑与底部高光，登录卡后「叠层玻璃」；按钮品牌蓝实心（仅提交中禁用，空字段仍走原 `validate()` 提示）；演示账号改为**一键登录**（原先需展开再点，共两次） |
| 首页概览 | 蓝色主卡左右紧凑布局、质控进度卡改浅色玻璃、指标卡缩小；页头范围改为眉标一行纯文字，右侧只留科室下拉、生成时间、刷新；缺陷分析三排分段控件合并为一行（统计对象分段 + 指标/排序下拉）；字号收敛为 12/13/14/20/32/48 六档 |
| 病历池 | 左列表 + 右预览；列宽收紧不再被预览遮挡；字号 12/13/14/20/32、标签表头不加粗、行高约 60px；「质控所选（0）」未选中时置灰；筛选区「一行半」（第一行搜索 + 住院状态，第二行日期/科室/医师统一下拉外观 + 查询/重置靠右，窄屏自动换行）；行内「查看」改浅灰胶囊；住院号改正文字体。**患者头像按用户要求保留** |
| 运行 / 终末病历质控 | 列表与病历池同构：患者 / 住院号、科室、问题摘要、最近质控、操作（「查看」胶囊）；整行点击切换右侧预览，「查看」直接打开完整质控结果（等同预览里的「查看完整结果」） |
| 质控规则（编码/首页/结算） | 共用组件 `src/components/rules/coding/*` 去 `font-black`，指标数字改 token 色，风险 high/medium/low 显示为中文色点，状态改 `mq-status` |
| 手术分级目录、自定义质控点 | 字重收敛（行内名称、分类、等级、按钮、标签降为 500），统计条改「标签在上、数字在下」 |
| 其余 v7.1 迁移页 | 系统配置、客户样本验证、质控反馈记录、统计分析、DRG/DIP、ICD、数据上传、数据管理、全屏病历详情、质控结果抽屉/卡片、查看病历弹窗（详见上一份交接文档） |

### 1.3 测试层面的改动

为适配新布局更新了断言（行为口径不变）：`QCOverviewView.spec.ts`（指标/排序由按钮点击改为下拉选值）、`QcRecordResultTable.spec.ts`（紧凑模式由 5 列改 6 列、「查看」发 `open-full`）、`QcRecordResultListView.spec.ts`（时间列序号、整行点击预览，并新增「查看打开完整结果」用例）、`workstationNav.spec.ts`（新增）等。

## 2. 合并前的事实（2026-09-28 实测）

| 项 | 值 |
| --- | --- |
| 分叉点 | `3dff664b4` 2026-09-27 记录发布范围复审通过及验收边界 |
| 源分支独有 | 55 个提交：`c10d2c745`（AGENTS 设计规范路径修正）+ UI 52 个（`03ffd81af`…`82c6f99fb`）+ 2 个交接文档提交 |
| 目标分支独有 | 4 个：`450f0e77f` 精简项目Agent指令、`14a5abe68` 合并已验收质控引擎及发布范围并保留精简指令、`4c835f9b0` 记录质控分支合并和浏览器冒烟结果、`cf698bafe` 修复正式质控事实被日志清洗删除导致保存失败（**仅本地，未推送**） |
| 目标独有改动的文件 | `apps/medqc-web/AGENTS.md`、`backend/app/services/sichuan_workspace_batch_worker.py`、一个三入口验收测试、`docs/acceptance/2026-09-27-lx0609-merge-browser-smoke.md`、`PROJECT_ROLLING_TODO.md` |
| 试合并冲突 | 2 个：`apps/medqc-web/AGENTS.md`、`apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md` |

### 2.1 两个冲突的处理口径

**`apps/medqc-web/AGENTS.md`：取目标分支的精简版，只修一处路径。**
目标分支把 AGENTS 精简了（`450f0e77f`），源分支只改过一行设计规范路径（`c10d2c745`）。精简版第 19 行仍写 `docs/gap/WorkstationV4-医疗浅色-DESIGN.md`，该路径**在目标分支上不存在**；实际文件是 `docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md`。处理：保留目标分支整份精简版，把其中 `docs/gap/WorkstationV4-医疗浅色-DESIGN.md` 改为 `docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md`，其余不动。

**`apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md`：两边新增条目都保留。**
两边都只在文件顶部新增了条目，按日期新到旧排列：源分支的「2026-09-28 工作台 UI 整改…」放最上，接着目标分支的两条 2026-09-27（「新任务保存失败最小修复…」「分支合并与浏览器冒烟…」），再接源分支的「2026-09-27 工作台 UI 迁移到 v7.1…」，下面是共同的原有内容。合并后把「2026-09-28 工作台 UI 整改」那条改成已合并的状态（写明合并提交号、目标分支名），不再提 `push-fix-clean` / `master`。

## 3. 合并步骤

### 3.1 推送源分支（需用户授权）

```bash
git -C C:/Users/Coldplay/.codex/worktrees/lx0609-rule-id-integration/LX888 push github codex/lx0609-rule-id-integration
```

### 3.2 在干净工作树里做合并

```bash
cd D:/LLM/LX888
git worktree add D:/LLM/LX888/.worktrees/ui-merge-20260928 -b merge/ui-into-tech-debt-20260928 codex/lx0609-tech-debt-20260730
cd D:/LLM/LX888/.worktrees/ui-merge-20260928
git merge --no-ff --no-commit codex/lx0609-rule-id-integration
git diff --name-only --diff-filter=U    # 应只有 AGENTS.md 与 PROJECT_ROLLING_TODO.md
```

按 2.1 手工解决两个冲突后：

```bash
git add apps/medqc-web/AGENTS.md apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md
git diff --cached --name-only | wc -l    # 应为源分支带入的文件 + 两个冲突文件，不应出现第 5 节列出的本地文件
git commit -F - <<'EOF'
合并工作台 UI 整改到日常主分支

- 带入 codex/lx0609-rule-id-integration 的 UI 整改（v7.1 迁移 + 侧栏/登录/首页/病历池/运行终末质控精修），仅展示层
- AGENTS.md 取日常分支精简版，并把 UI 设计规范路径修正为 docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md
- PROJECT_ROLLING_TODO.md 保留两边新增条目
EOF
```

### 3.3 验收（第 4 节）通过后，让目标分支快进

主工作区有已暂存的改动，快进前先确认不会覆盖（已知 `SingleRecordQcResultPanel.spec.ts` 重叠，见第 0 节第 3 条；git 提示会覆盖本地修改时**停下来问用户**，不要 stash 或丢弃）：

```bash
cd D:/LLM/LX888
git merge --ff-only merge/ui-into-tech-debt-20260928
git status --short    # 原有未提交改动应原样保留
# 经用户授权后再推送；目标分支本地已领先 github 1 个提交（cf698bafe），推送会一并推上去
# git push github codex/lx0609-tech-debt-20260730
```

完成后可在用户同意下删除临时工作树与临时分支：`git worktree remove D:/LLM/LX888/.worktrees/ui-merge-20260928`、`git branch -d merge/ui-into-tech-debt-20260928`。

## 4. 合并后的验收

在合并工作树的 `apps/medqc-web` 下：

```bash
npm ci
npm run check:encoding
npx eslint .            # npm run lint 带 --fix 会改文件；只检查请用 npx eslint
npm run type-check
npm run test:unit
```

- **单测基线**：源分支在 UTC-5 机器上 1131 个里 1128 个通过；3 个失败依赖北京时区（`tests/utils/date-utils.test.ts` 2 个、`QCOverviewView.spec.ts`「将数据运行状态组织为可扫描的状态单元」1 个），目标分支记录里也是同样 3 个时区断言，固定 `Asia/Shanghai` 后通过。`CustomerSampleValidationView.spec.ts` 偶发超时，单独重跑通过。出现这之外的失败才需要排查。
- 目标分支 `cf698bafe` 改了后端 `sichuan_workspace_batch_worker.py` 并新增三入口验收测试，按目标分支原有口径跑相关 pytest。
- **页面抽查**（后端 8001、前端 `npm run dev -- --port 3100 --strictPort`，用 `127.0.0.1` 访问）：在 1440×900、1280×800、1024×768 下看登录页（演示账号一键登录）、首页、侧栏（折叠/展开、图标模式）、病历池（筛选区一行半、列表不被预览遮挡）、运行/终末病历质控（列表与病历池一致、「查看」打开完整结果）、质控规则四个页签、自定义质控点、手术分级目录。截图含患者姓名，文件名须以 `-private` 结尾且不得提交。
- 目标分支冒烟记录中已知「历史任务详情 409 却显示空列表」问题，与 UI 整改无关，不要当作本次合并引入。

## 5. 不要带入的本地内容

- **源分支 worktree 的未提交改动**（与 UI 无关）：`apps/medqc-web/backend/app/services/luxian_0609/` 下 6 个执行器 `.py`（目标分支冒烟记录里提到的「另一个工作树六个执行器未提交修改」就是这些）、`apps/medqc-web/src/styles/index.prebuilt.css`；未跟踪的 `.claude/`、`apps/medqc-web/backend/data/luxian_0609_opinion_freeze/`；`.tmp/` 下的截图与脚本（已 gitignore，含患者信息）。这些都不在提交里，按第 3 节合并不会带入。
- **主工作区 `D:\LLM\LX888` 的未提交改动**：属于其他进行中的工作，合并过程中保持原样。

## 6. 已知问题与未完成事项

| 事项 | 说明 |
| --- | --- |
| 中文字体 | `src/styles/source-han-sans-sc.css` 声明了思源黑体，但 `public/fonts/source-han-sans-sc/` 下没有字体文件，Windows 实际回退到微软雅黑（只有常规/粗体两档），这是「字发黑」的根因之一。是否打包字体（约数 MB，可用 WOFF2 减轻）待用户决定 |
| 运行/终末质控日期筛选 | 仍是浏览器原生日期输入（「年-月-日」），未统一成病历池的下拉样式 |
| 重复错误提示 | 语义规则、客户样本验证、系统配置等页进入时会连弹多条相同报错，未处理 |
| 真实质控结果 | 质控结果相关页面尚未用真实完成数据复核观感 |
| 旧样式清理 | 部分页面保留了被 v7.1 覆盖的旧样式（多层 `!important`），后续可清理；本轮只在必要处直接修源规则（如病历池筛选区 600 字重） |
| 设计画布 v8 | 设计画布上的 v8 / v8.1「苹果规范版」只是探索稿，**未采用、未落代码** |

## 7. 第二轮增量合并（2026-09-28）

### 7.1 增量内容

目标分支 `29c9ead09` 已带入源分支到 `e1a003b7c`。之后源分支新增 3 个提交（`e1a003b7c..b46f0e303`，7 个文件，+386/−27，只动展示层与文档）：

| 提交 | 内容 |
| --- | --- |
| `b5f10635f` | 质控结果右侧栏阅读优化：卡片**收起时只显示标题、状态、规则号、一句结论**；「逐次检查核对」「修改建议」改为点「反馈与详情」展开后才显示；逐次核对默认只列需处理的次数（未记录/待核实），已记录等其余次数折叠为「另有 N 次：已记录 1」；逐次明细行只展示、**不可点击**（数据里没有每次检查→具体文书的对应关系，不推测）；修改建议新增 `compact` 侧栏排版（修改对象作标签、注意事项弱化，四段原文逐字保留）；规则级证据入口文案「可定位原文 / 定位原文」改为「可查看相关文书 / 查看相关文书」；复制调试信息改为图标按钮（文字留给读屏） |
| `845193c5a` | 本交接文档补充与主工作区未提交文件的重叠说明 |
| `b46f0e303` | 展开详情轻量化：规定时限与判定事实合并成左对齐「标签 内容」列表（「判定事实」分组标题只留给读屏），证据 / 反馈收为细行，「修改建议」标题降为 12px 灰色；只改样式 |

涉及文件：`SingleRecordQcResultPanel.vue`、`ExamLabEventResultBlock.vue`（`customer-sample-validation/`）、`components/qc/QcRemediationSuggestion.vue` 及其 spec、`tests/unit/.../SingleRecordQcResultPanel.spec.ts`、`PROJECT_ROLLING_TODO.md`、本文档。**未改** API、Store、后端合同、判据、质控结论与证据数据。

### 7.2 试合并结果（`git merge-tree`，目标 `29c9ead09`）

- 只有 1 个冲突：`apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md`（两边都在顶部加了条目）。
- 处理口径：以目标分支版本为底，把源分支新增的「2026-09-28 质控结果右侧栏阅读优化（仅前端展示）…」整段放在最上面，其余保留目标分支原样；在这段末尾补一句「已于 `<合并提交号>` 合并到 `codex/lx0609-tech-debt-20260730`」。
- 代码文件无冲突。

### 7.3 ⚠ 需要先请用户确认的方向冲突

主工作区 `D:\LLM\LX888` 对 `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts` 有未提交修改（只改了两个用例标题）：

- 「默认以紧凑摘要展示…」→「**默认展示修改建议**，客户可明确展开和收起其余完整详情」
- 「展开后展示完整判定、逐项判定、证据、医学分析与建议」→「…**修改建议保持常显**」

这与 `b5f10635f`「修改建议改为展开后才显示」方向相反（该设计经用户在设计画布上确认）。另外主工作区 `CustomerQcResultDetailCard.vue` 也有未提交修改（删 1 行），属于另一个页面，本次合并不涉及。

- 合并前先问用户：修改建议是「收起时也常显」还是「展开后才显示」。**不要自行二选一**。
- 若用户要常显：合并后只需把 `SingleRecordQcResultPanel.vue` 里 `QcRemediationSuggestion` 的 `v-if` 去掉 `expandedKey === item.key &&` 这一项，并同步改对应 spec 断言；紧凑排版可保留。
- 快进时 git 会因这个 spec 的本地修改拒绝，这是安全拒绝；由用户决定先提交还是另行处理，不要 stash / reset / checkout。

### 7.4 步骤

```bash
# 1. 推送源分支（需用户授权）
git -C C:/Users/Coldplay/.codex/worktrees/lx0609-rule-id-integration/LX888 push github codex/lx0609-rule-id-integration

# 2. 干净工作树合并
cd D:/LLM/LX888
git worktree add D:/LLM/LX888/.worktrees/ui-merge-2 -b merge/ui-round2-20260928 codex/lx0609-tech-debt-20260730
cd D:/LLM/LX888/.worktrees/ui-merge-2
git merge --no-ff --no-commit codex/lx0609-rule-id-integration
git diff --name-only --diff-filter=U    # 应只有 PROJECT_ROLLING_TODO.md
# 按 7.2 解决后
git add apps/medqc-web/docs/plans/PROJECT_ROLLING_TODO.md
git commit -m "合并质控结果右侧栏阅读优化（第二轮 UI 增量）"

# 3. 验收（apps/medqc-web 下）
npm ci && npm run check:encoding && npm run type-check
npx eslint src/views/workstation-v4/customer-sample-validation src/views/workstation-v4/components/qc
TZ=Asia/Shanghai npm run test:unit

# 4. 用户确认 7.3 后，主工作区快进
cd D:/LLM/LX888 && git merge --ff-only merge/ui-round2-20260928
```

### 7.5 验收要点

- 单测：源分支相关 20 个文件 220 项通过；全量基线同第 4 节（Asia/Shanghai 下应全过）。
- 浏览器：客户样本验证页 → 任一病历「查看结果」→ 找一条 CT/MRI「24 小时内在病程中未记录」：收起时无逐次核对和修改建议；点「反馈与详情」后逐次核对只列 2 次「未记录」、底部「另有 1 次：已记录 1」可展开、明细行鼠标为默认箭头且无按钮；规定时限 / 已核对病程为左对齐列表；证据行文案为「3 份，可查看相关文书」，点开后能定位文书。截图含患者信息，文件名以 `-private` 结尾。
- 其他使用 `QcRemediationSuggestion` 的页面不传 `compact`，保持原表格样式（有单测覆盖）。
