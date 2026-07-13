# AGENTS Rules For Codex

## Scope

- Default scope is this monorepo.
- Frontend app focus: `apps/medqc-web`.

## 多 Agent 协作与架构责任

- 主协调 Agent 是项目大脑和最终责任人，不能只转发实现 Agent 的方案、进度或结论，也不能把需求分析、架构判断和验收判断整体外包。
- 主协调 Agent 在派发开发任务前，必须亲自核对业务目标、真实代码调用链、现有数据/测试证据和历史问题，明确根因、预期收益、最小改动范围、失败语义与验证方案。
- 实现 Agent 是执行者，只按主协调 Agent 已明确的方案、文件白名单和验收标准编码、测试与提交；不得自行扩大范围、改变架构方向或用局部单测替代业务效果证明。
- 测试/审查 Agent 负责独立证伪，重点检查真实业务结果、回归影响、性能数据和边界条件；测试通过不等于业务目标达成。
- 主协调 Agent 必须亲自审查关键 diff、模型输入、状态映射、调用次数、性能数据和真实病例回归结果，不能仅凭 `READY_FOR_REVIEW`、测试数量或 Agent 报告接受实现。
- 每次任务开始前，主协调 Agent 至少给出：问题证据、根因判断、实施方案、文件范围、验收指标和剩余风险；证据不足时先做只读调查，不得让实现 Agent 猜测开发。
- 优先采用 1-2 个业务点的小闭环：真实问题 -> 最小修改 -> 聚焦测试 -> 真实数据复核 -> 性能/准确性对比。没有准确率、耗时或客户体验收益证据的架构扩展不得继续投入。
- 多 Agent 并发只用于加速已明确且相互独立的执行或验证工作；并发不能替代主协调 Agent 的统一设计、取舍和最终验收责任。

## Development Rules

- Use UTF-8 without BOM for all text files.
- Keep line endings as LF.
- Do not introduce new `.vue.ts` mirror files.
- Do not bypass type errors by broad `any` changes in shared types.
- Prefer fixing type boundaries (`api dto`, `store state`, `component props/emits`) over local casts.

## Frontend UI/UX Rules

- `workstation-v4` 页面必须优先遵循 `apps/medqc-web/docs/gap/WorkstationV4-医疗浅色-DESIGN.md`。
- 医疗工作台 UI 默认采用浅色医疗中后台风格：浅背景、白色卡片、弱边框、轻阴影、清晰信息层级；不要使用深色大背景、营销化头图或高饱和装饰。
- 页面结构优先按“总览/筛选/明细/结果”分层，复杂功能必须拆成可扫描的区块，不要把创建、编辑、执行、结果全部平铺在同一大表单里。
- 组件交互遵循 Vue Pro / Ant Design Vue 的中后台模式：清晰工具栏、主次按钮分明、筛选项聚合、弹窗/抽屉承载复杂创建或编辑流程。
- 质控结果、病历文书、批量任务等高密度页面应优先保证可读性：问题卡片/分组摘要优先于窄表格；避免窄列导致中文逐字换行。
- 新增或重构前端页面时，优先复用现有 `workstation-v4` CSS token、布局容器和组件风格，不另起一套视觉语言。
- 不为纯展示效果修改后端接口契约；如必须改接口，先明确兼容字段和回退策略。

## Prohibited Actions

- Do not commit generated build output (`dist/`, coverage artifacts, temp logs).
- Do not disable CI gates in workflow files to force green.
- Do not add `@ts-ignore`; use `@ts-expect-error` with a short reason when unavoidable.

## Required Checks Before Commit

Run in `apps/medqc-web`:

1. `npm run check:encoding`
2. `npm run lint`
3. `npm run type-check`
4. `npm run test:unit`

If full checks are too heavy locally, run at least:

1. `npm run check:encoding`
2. `npm run lint`

## TypeScript Migration Strategy

- Keep `tsconfig.json` as compatibility config for mixed JS/TS.
- Use `tsconfig.strict.json` for strict migration work (`npm run type-check:strict`).
- Migrate module-by-module:
  1. Define/adjust shared types first.
  2. Fix API layer typing.
  3. Fix store typing.
  4. Fix component props/emits and view integration.
- For new modules, require strict typing from day one.

## Encoding Guardrails

- Enforce `.editorconfig` + `.gitattributes`.
- Keep `npm run check:encoding` in local and CI quality gates.
- If mojibake appears, fix source file encoding first, then content.

## 基本偏好

- 使用中文进行沟通和代码注释。
- commit message 使用中文。
- 使用 UTF-8。

## 终端命令安全策略

- 自动执行：文件读取、目录浏览、git status/log/diff、python/node 脚本执行、npm/pip install、dev server 启动、测试运行。
- 需要确认：文件删除(del/rm/rmdir)、git push/force、全局包安装(npm -g)、数据库写操作。

## 开发习惯

- 每完成一个功能修改或 bug 修复后，主动使用 /commit workflow 提交代码。
