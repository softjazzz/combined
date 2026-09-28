# 工作台 UI 整改 · 合并主干交接文档

> 交接日期：2026-09-28 ｜ 源分支：`codex/lx0609-rule-id-integration`（本地领先 `github/codex/lx0609-rule-id-integration` 53 个提交，**未推送**）
> UI 提交范围：`03ffd81af^..82c6f99fb`（52 个提交；领先上游的另 1 个是 UI 之前的 `c10d2c745` AGENTS 路径修正）
> 上一份交接（v7.1 迁移本身）：[2026-09-27-ui-v71-handoff.md](2026-09-27-ui-v71-handoff.md) ｜ 设计规范：[WorkstationV4-医疗浅色-DESIGN.md](../0418/UI/WorkstationV4-医疗浅色-DESIGN.md)

## 0. 先读这三条

1. **UI 改动没法单独摘出来合并。** UI 提交改到的 150 个文件里，有 41 个在 `origin/push-fix-clean` 上根本不存在（运行/终末质控、客户样本验证、手术分级目录、病历池预览等页面本身就是本分支早先做的功能）。所以「把 UI 合并到主干」实际等于「把整个 `codex/lx0609-rule-id-integration` 分支合并到主干」，会同时带入 LX0609 规则集成等全部分支工作（约 2500+ 个提交）。**动手前请与用户确认这一点。**
2. **先确认主干是哪条分支。** 仓库配置里的主干是 `origin/push-fix-clean`（`origin` 指向本机 `D:\LLM\lx0222\health-qc-monorepo`），但 GitHub 远程 `github` 上没有这个分支，只有 `master`。不同目标的合并难度完全不同，见第 4 节。
3. **UI 整改只改了展示层。** 150 个文件分布：`src/views` 117、`src/components` 14、`tests` 8、`src/styles` 4、`docs` 4、`tailwind.config.js`、`src/main.ts`、`src/App.vue` 各 1；**没有改** `src/api`、`src/stores`、`src/services`、`src/router`、`src/types`、`src/domain`、后端任何文件，也没有改业务流程、筛选项或接口契约。

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
| 病历池 | 左列表 + 右预览；列宽收紧不再被预览遮挡；字号 12/13/14/20/32、标签表头不加粗、行高约 60px；「质控所选（0）」未选中时置灰；筛选区整理为「一行半」（第一行搜索 + 住院状态，第二行日期/科室/医师统一下拉外观 + 查询/重置靠右，窄屏自动换行）；行内「查看」改浅灰胶囊；住院号改正文字体。**患者头像按用户要求保留** |
| 运行 / 终末病历质控 | 列表与病历池同构：患者 / 住院号、科室、问题摘要、最近质控、操作（「查看」胶囊）；整行点击切换右侧预览，「查看」直接打开完整质控结果（等同预览里的「查看完整结果」） |
| 质控规则（编码/首页/结算） | 共用组件 `src/components/rules/coding/*` 去 `font-black`，指标数字改 token 色，风险 high/medium/low 显示为中文色点，状态改 `mq-status` |
| 手术分级目录、自定义质控点 | 字重收敛（行内名称、分类、等级、按钮、标签降为 500），统计条改「标签在上、数字在下」 |
| 其余 v7.1 迁移页 | 系统配置、客户样本验证、质控反馈记录、统计分析、DRG/DIP、ICD、数据上传、数据管理、全屏病历详情、质控结果抽屉/卡片、查看病历弹窗（详见上一份交接文档） |

### 1.3 测试层面的改动

为适配新布局更新了断言（行为口径不变）：`QCOverviewView.spec.ts`（指标/排序由按钮点击改为下拉选值）、`QcRecordResultTable.spec.ts`（紧凑模式由 5 列改 6 列、「查看」发 `open-full`）、`QcRecordResultListView.spec.ts`（时间列序号、整行点击预览，并新增「查看打开完整结果」用例）、`workstationNav.spec.ts`（新增）等。

## 2. 提交清单

```bash
git log --reverse --oneline 03ffd81af^..82c6f99fb
```

起点 `03ffd81af 新增设计 Token v2 并全局加载`，终点 `82c6f99fb 运行 / 终末质控列表「查看」字号改回 12px`。其中 `fc649abcd`（登录页重设计）已被 `1fe978feb` revert，属于正常历史，无需处理。

## 3. 合并前的事实（2026-09-28 在本分支实测）

| 候选主干 | 最后提交 | 本分支领先 | 它领先本分支 | 结论 |
| --- | --- | --- | --- | --- |
| `github/master` = `origin/master` | `ee5ec2f99`（2025-11-25） | 2747 | 0 | 可快进，无冲突 |
| `combined0616/main` | `f492a4b9c`（2026-06-14） | 1953 | 0 | 可快进，无冲突 |
| `origin/push-fix-clean` | `d5df61df3`（2026-04-13） | 2571 | 124 | 已分叉，见下 |

`origin/push-fix-clean` 的情况：

- 分叉点 `6913171e2`。主干那 124 个提交里，**122 个已按相同补丁进入本分支**（`git cherry HEAD origin/push-fix-clean` 显示 122 个 `-`）；只有 2 个没有：
  - `4d76e2d24 fix: 清除 sichuanDipData.ts GBK 乱码…`（2026-03-20，458 个文件、+231 万行，是一次大检查点，含 `OpenDRG` 子模块指针与大量源码）；本分支之后已单独修过 `sichuanDipData.ts`（`a4374d77f`）。
  - `b90123cb3 feat: 汇总工作台改造与本地启动稳定性增强`（2026-03-24，76 个文件，主要是 `docs/acceptance`、`scripts`、`workstation-v2` 同步控制台、`components/rules/coding`）。
- 主干在 git 里跟踪了约 **44,724 个 `node_modules/` 文件**；本分支已全部移除。
- `git merge-tree` 试合并：**519 个冲突文件**（前端源码约 232、后端约 76、`node_modules` 若干，其余为脚本与配置）。冲突主要来自「同一补丁在两边以不同提交号存在」，不是真正的两套改动打架。

## 4. 合并方法

> 通用约束（来自 AGENTS.md）：推送、强推、删除需用户明确授权；按路径暂存，不要 `git add -A`；提交信息中文；不要带入第 6 节列出的本地未提交文件。

### 4.1 先把源分支推上去（需用户授权）

```bash
git push github codex/lx0609-rule-id-integration
```

### 4.2 情况 A：主干是 `master`（github / origin）或 `combined0616/main`

主干完全包含于本分支，直接快进：

```bash
git fetch --all
git switch master                     # 或对应主干分支
git merge --ff-only codex/lx0609-rule-id-integration
# 跑第 5 节验收后，经用户授权再推送
```

### 4.3 情况 B：主干是 `origin/push-fix-clean`

在独立集成分支上完成合并，验收通过后让主干快进到集成分支，主干历史不被改写。

```bash
git fetch origin
git switch -c integrate/ui-v71-to-push-fix-clean codex/lx0609-rule-id-integration
```

**第一步：核对两个未进入本分支的旧提交是否还需要。**

```bash
git show --stat 4d76e2d24
git show --stat b90123cb3
# 逐个文件看主干版本与本分支当前版本的差异，判断是否已被本分支覆盖
git diff HEAD origin/push-fix-clean -- <上面列出的文件路径>
```

**第二步，按核对结果二选一：**

- **B1（推荐，前提是确认这两个提交的内容都已被本分支覆盖或不再需要）**：记录主干为已合并，但树完全保持本分支内容，一次性消除 519 个伪冲突。

  ```bash
  git merge -s ours --no-ff origin/push-fix-clean \
    -m "合并 push-fix-clean：主干 124 个提交中 122 个已按补丁并入本分支，其余 2 个检查点提交经核对已被覆盖"
  ```

- **B2（其中有需要保留的内容时）**：正常合并，冲突默认取本分支，再手工补回需要的主干内容。

  ```bash
  git merge --no-ff --no-commit origin/push-fix-clean
  git diff --name-only --diff-filter=U > .tmp/merge-conflicts.txt
  # node_modules：保持本分支的删除
  grep '^node_modules/' .tmp/merge-conflicts.txt | xargs -r git rm -q --
  # 其余内容冲突：默认取本分支版本（本分支已包含主干 122/124 的补丁）
  grep -v '^node_modules/' .tmp/merge-conflicts.txt | xargs -r git checkout --ours --
  # 「本分支已删、主干修改过」的文件 checkout --ours 会失败，这类确认后用 git rm
  # 然后检查主干无冲突带进来的新增文件（如 OpenDRG 子模块指针、docs/acceptance、node_modules）是否需要
  git diff --cached --stat codex/lx0609-rule-id-integration
  # 对需要保留的主干内容，从 origin/push-fix-clean 按路径取回：git checkout origin/push-fix-clean -- <path>
  ```

  确认无误后按路径暂存并提交合并。

**第三步：验收（第 5 节）通过后，让主干快进到集成分支。**

```bash
git switch push-fix-clean
git merge --ff-only integrate/ui-v71-to-push-fix-clean
# 经用户授权再推送：git push origin push-fix-clean
```

## 5. 合并后的验收

在 `apps/medqc-web` 下：

```bash
npm ci
npm run check:encoding
npx eslint .            # npm run lint 带 --fix，会改文件；只检查请用 npx eslint
npm run type-check
npm run test:unit
```

- **单测基线（本分支，时区 UTC-5 的机器）**：1131 个里 1128 个通过；3 个失败都依赖北京时区（`tests/utils/date-utils.test.ts` 2 个、`QCOverviewView.spec.ts`「将数据运行状态组织为可扫描的状态单元」1 个），与 UI 无关，已另开任务修复；`CustomerSampleValidationView.spec.ts` 偶发失败，单独重跑 67/67 通过。出现这之外的失败才需要排查。
- 本分支还带有后端改动（LX0609 规则集成），按 AGENTS.md 另跑相关 pytest。
- **页面抽查**（后端 8001、前端 `npm run dev -- --port 3100 --strictPort`，用 `127.0.0.1` 访问）：在 1440×900、1280×800、1024×768 下看登录页（演示账号一键登录）、首页、侧栏（折叠/展开、图标模式）、病历池（筛选区一行半、列表不被预览遮挡）、运行/终末病历质控（列表与病历池一致、「查看」打开完整结果）、质控规则四个页签、自定义质控点、手术分级目录。截图含患者姓名，文件名须以 `-private` 结尾且不得提交。

## 6. 不要带入主干的本地内容

源分支工作区当前有以下**未提交**改动，与 UI 无关、不属于本次合并：

- `apps/medqc-web/backend/app/services/luxian_0609/` 下 6 个 `.py`（`native_mdt_execution.py`、`native_surgery_document_execution.py`、`native_surgery_gate_execution.py`、`native_transfusion_execution.py`、`native_tumor_pathology_execution.py`、`rescue_record_completeness.py`）——他人进行中的后端工作；
- `apps/medqc-web/src/styles/index.prebuilt.css`；
- 未跟踪：`.claude/`、`apps/medqc-web/backend/data/luxian_0609_opinion_freeze/`；
- `.tmp/` 下的截图与脚本（已被 gitignore，含患者信息）。

## 7. 已知问题与未完成事项

| 事项 | 说明 |
| --- | --- |
| 中文字体 | `src/styles/source-han-sans-sc.css` 声明了思源黑体，但 `public/fonts/source-han-sans-sc/` 下没有字体文件，Windows 实际回退到微软雅黑（只有常规/粗体两档），这是「字发黑」的根因之一。是否打包字体（约数 MB，可用 WOFF2 减轻）待用户决定 |
| 运行/终末质控日期筛选 | 仍是浏览器原生日期输入（「年-月-日」），未统一成病历池的下拉样式 |
| 重复错误提示 | 语义规则、客户样本验证、系统配置等页进入时会连弹多条相同报错，未处理 |
| 真实质控结果 | 质控结果相关页面尚未用真实完成数据复核观感 |
| 旧样式清理 | 部分页面保留了被 v7.1 覆盖的旧样式（多层 `!important`），后续可清理；本轮只在必要处直接修源规则（如病历池筛选区 600 字重） |
| 设计画布 v8 | 设计画布上的 v8 / v8.1「苹果规范版」只是探索稿，**未采用、未落代码** |
