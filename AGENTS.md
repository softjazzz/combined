# AGENTS Rules For Codex

## Scope
- Default scope is this monorepo.
- Frontend app focus: `apps/medqc-web`.

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
- 使用中文进行沟通和代码注释
- commit message 使用中文
- 使用 UTF-8

## 终端命令安全策略
- 自动执行：文件读取、目录浏览、git status/log/diff、python/node 脚本执行、npm/pip install、dev server 启动、测试运行
- 需要确认：文件删除(del/rm/rmdir)、git push/force、全局包安装(npm -g)、数据库写操作

## 开发习惯
- 每完成一个功能修改或 bug 修复后，主动使用 /commit workflow 提交代码
