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
