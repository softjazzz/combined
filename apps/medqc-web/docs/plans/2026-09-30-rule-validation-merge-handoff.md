# 规则验收 · 合并交接说明

> 日期：2026-09-30 ｜ 源分支：`codex/rule-validation`（工作树 `C:\Users\Coldplay\.codex\worktrees\rule-verify\LX888`，未推送）
> 源分支 HEAD：`278d98d79`（本文所在提交之后以 `git log` 为准）｜ 基点：`26cbbf129`
> 目标分支：`codex/lx0609-tech-debt-20260730`（主工作区 `D:\LLM\LX888`，HEAD 仍为 `26cbbf129`）
> 需求与设计：[2026-09-28-rule-validation-release-workflow.md](2026-09-28-rule-validation-release-workflow.md)（PRD，附录 A/B/C 为实现与验证记录）

## 一句话结论

源分支是以规则为中心的新版“规则验收”，**取代**了 codex 旧版“单病例验收抽屉”（`493cc418b`、`b98138520`，以及分支 `codex/validation-integration` 的 `b0b790a6a`）。Git 层面目标分支停在基点上，可以快进；**真正的难点是主工作区里还留着旧版的未提交改动，与新版冲突**。合并时必须保留主工作区的其他工作，同时去掉旧版验收代码。

## 1. 源分支内容（`26cbbf129..278d98d79`，11 个提交，42 个文件）

| 提交 | 内容 |
| --- | --- |
| `493cc418b` `b98138520` | codex 旧版单病例验收与材料冻结（后续提交已撤除或删除，保留在历史里） |
| `7806cbfeb` | 按用户原始意图重写 PRD，删除过时的 `2026-09-28-rule-validation-implementation.md` |
| `96f5f96ba` | 禁止对自建测试池执行源库匹配和同步（后端 6 个入口拦截，前端菜单置灰） |
| `b9c22ff23` `85c7d0804` | 撤除材料冻结（`execution.py` 和 batch worker 恢复到 `26cbbf129`，删除 ContextVar 模块），改为测试病例固定“评价时间点” |
| `e82fda2b0` | 新后端 `/api/v1/qc/rule-validation`，新表 `rule_validation_runs` 和 `rule_validation_events`（首次使用时自动建表） |
| `7c5cdefa4` | 新前端：导航“规则 → 规则验收”、列表、详情、核对抽屉、批准弹窗；**删除**旧抽屉、`test_case_validation.py`、`/test-records/{id}/validation*` |
| `9dee5b1ae` | 0609 规则列表新增“发布范围”列、筛选和“去验收”按钮 |
| `16d9c6b5b` | 规则验收内的新建和复制测试病例页，修复浏览器实测发现的 12 个问题（PRD 附录 B） |
| `278d98d79` | 第 5 步：`luxian_0609/impact_scope.py` 声明影响范围，B 类规则按上线后范围运行并做同族回归（PRD 附录 C） |

源分支的**最终状态**：`backend/app/services/luxian_0609/execution.py` 和 `backend/app/services/sichuan_workspace_batch_worker.py` 与 `26cbbf129` 一致。以下文件都**不存在**：`test_case_validation.py`、`test_case_validation_context.py`、`RuleValidationDrawer.vue`、`test-case-validation-service.ts`。

## 2. 主工作区现状（2026-09-30 核对）

主工作区有大量未提交改动，属于多个任务。其中**旧版验收**是 codex 在 09-29 用三方合并直接写进工作区的（见主工作区未跟踪文档 `2026-09-29-rule-validation-integration.md`），一直没有提交。

### 2.1 属于旧版验收、合并时应丢弃

未跟踪文件（新版已删除或替换）：

- `backend/app/services/test_case_validation.py`、`test_case_validation_context.py`
- `backend/tests/integration/test_test_case_validation_chain.py`、`backend/tests/unit/test_test_case_validation.py`
- `src/services/test-case-validation-service.ts`
- `src/views/workstation-v4/customer-sample-validation/RuleValidationDrawer.vue` 及其测试
- `docs/plans/2026-09-28-rule-validation-implementation.md`（已由用户决定删除）
- `docs/plans/2026-09-28-rule-validation-release-workflow.md`：**这是旧版 PRD**，以源分支版本为准
- `docs/plans/2026-09-29-rule-validation-integration.md`：旧版的接入记录。建议删除，或在开头注明“已被 2026-09-30 规则验收取代”，由用户决定

已跟踪文件中属于旧版的改动块，要在合并时剔除：

- `backend/app/services/luxian_0609/execution.py`：主工作区的改动**全部**是旧版材料冻结（引入 `test_case_validation_context`、`build_validation_execution_session`、`validation_material_active`），应整体丢弃，恢复为源分支版本。
- `backend/app/services/sichuan_workspace_batch_worker.py`：改动**混有**旧版冻结和“逐病例计时”（另一任务）。保留计时，去掉冻结或验收相关部分。
- `backend/app/routers/qc_sample_pools.py`、`custom_qc_sample_pool_service.py`：混有旧版 `/test-records/{id}/validation*` 接口和“创建接口提速”等其他工作。源分支也改了这两个文件（测试池拦截、评价时间点、测试病例复制），需要逐块合并：删掉旧验收接口，保留其他工作和源分支的改动。
- `src/views/workstation-v4/CustomerSampleValidationView.vue`：去掉旧抽屉入口，保留其他样式和修复改动。
- `backend/tests/unit/test_luxian_0609_formal_extension_chain.py`、`test_luxian_0609_native_exam_lab_execution.py`：命中了 `golden_answers`、`evaluation_as_of` 等关键词，需要判断是旧验收断言还是其他任务的断言。
- `docs/plans/PROJECT_ROLLING_TODO.md`：两边都改了，手工合并，保留双方条目。

### 2.2 与源分支重叠、但不属于旧版验收（保留）

`src/views/workstation-v4/semantic-rules/`（`SemanticRulesWorkspace.vue`、`SemanticRulesTableSection.vue`、`service.ts`、`types.ts`）两边都改了。源分支加的是“发布范围”列、筛选和“去验收”跳转；主工作区的改动来自其他任务。需要逐块合并，两边都保留。

### 2.3 与本任务无关（不要带进合并提交，也不要丢）

规则目录 JSON（包括 CT 规则改为 `default`，见 `2026-09-28-ct-default-release.md`）、`luxian_0609/*` 下的执行器和映射、出院记录相关的新文件、`local_cdm_*`、`tmp-*`、`.worktrees/`、`apps/medqc-web - 副本/`、`src/styles/index.prebuilt.css`（dev server 自动生成）等。

## 3. 建议合并步骤

**前提**：在主工作区动手前，先征得用户同意，决定如何处理其他任务的未提交改动。按项目规则，不得使用裸 `git stash` 或 `reset`，删除操作也要用户授权。

1. 先把主工作区里**不属于旧版验收**的改动，由各自的负责人或经用户确认后，按路径提交到目标分支。例如：逐病例计时、创建接口提速、semantic-rules 的其他改动、CT 发布等。提交时剥掉 §2.1 列出的旧版改动块，确保目标分支上没有任何旧验收代码。
2. 删除 §2.1 的未跟踪旧文件（需要用户授权）。它们会阻止合并，而且与新版冲突。
3. 在目标分支上执行 `git merge codex/rule-validation`。如果第 1 步已经产生新提交，就用普通合并；没有的话可以快进。按 §2 逐块解决冲突，结果以源分支的规则验收实现为准。
4. 用 `git grep -nE "test_case_validation|RuleValidationDrawer|test-case-validation|validation_material_active"` 确认没有残留引用（`docs/` 下的历史记录除外）。
5. `codex/validation-integration`（`b0b790a6a`）**不要合并**。它是旧版的延续，已被取代。它修的问题是“验收规则选择器要和正式可选范围取交集，否则被客户排除的 5 条规则能保存却不能运行”。合并后要核对新版有没有同样的问题：待验收列表和运行入口里，会不会出现被客户排除、实际跑不起来的规则。如果有，在新版的 `rule_validation.py` 目录读取处补上同样的交集。

## 4. 合并后必跑的检查

在 `apps/medqc-web` 目录下运行：

```bash
npm run check:encoding && npm run lint && npm run type-check
```

```bash
npx vitest run tests/unit/views/workstation-v4/rule-validation tests/unit/views/workstation-v4/semantic-rules tests/unit/views/workstation-v4/SyntheticCaseBuilder.spec.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts src/components/layout/__tests__/workstationNav.spec.ts
```

后端（主工作区有 `backend/.env`，可以直接跑；没有 `.env` 时，见 §6 的 SQLite 跑法）：

```bash
python -m pytest tests/unit/test_rule_validation_service.py tests/unit/test_luxian_0609_impact_scope.py tests/unit/test_customer_test_pool_fixed.py tests/unit/test_test_case_evaluation_date.py tests/integration/test_rule_validation_chain.py -q
```

然后跑全量前端单测，以及主工作区其他任务相关的后端测试（逐病例计时、样本池路由等），确认合并没有破坏它们。

已知基线：前端全量里有 3 项失败，都是本机美国中部时区导致的（`date-utils` 2 项、`QCOverviewView` 1 项），与本功能无关。`CustomerSampleValidationView` 在全量跑时偶尔超时，单独跑能通过。

## 5. 验证现状与未完成事项

- 第 1–4 步已在浏览器和本机 PG 上端到端验证过（规则 `LX0609-09-01-02`，4 个合成病例，2 次真实模型调用，见 PRD 附录 B）。
- 第 5 步（同族回归）只做了单测和 SQLite 集成测试，**没有在浏览器和 PG 上实测**。建议合并后用一条 B 类规则（如 `06-01-03`）实测一次。
- 已知限制：已上线规则在平台上没有“验收通过”记录，所以目前所有 B 类同族规则都会显示为“无保护集”，只能靠缺口说明放行（见 PRD 附录 C）。
- 待做：第 6 步试点。从 0916 迁入原 025 和原 031，需要真实病例。
- 本机 PG 里已有测试数据：4 个“【验收测试】”病例，一次运行、核对、结论和批准的记录，以及自动建好的两张新表。这些不影响合并。如需清理，要用户授权后再写 SQL。

## 6. 环境提示

- 在源工作树跑后端测试（没有 `.env`）：

```bash
JWT_SECRET=test-only-secret-for-unit-tests-0123456789 DATABASE_URL="sqlite:///<临时目录>/unit.db" python -m pytest <测试文件> -q -p no:cacheprovider
```

- `vue-tsc` 可能因内存不足崩溃，加上 `NODE_OPTIONS=--max-old-space-size=8192` 即可跑通。
- 浏览器实测时，后端用 `--env-file D:/LLM/LX888/apps/medqc-web/backend/.env` 启动，端口 8001；前端端口 3000，只监听 `127.0.0.1`。参考源工作树根目录的 `.claude/launch.json`，这个文件不入库。
- 推送源分支、推送目标分支都需要用户授权。
