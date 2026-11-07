# 模型配置治理 V7.1 界面收口

## 范围与依据

基线为 `c3bd7524a53a18cd6cecf1a6348e3f1db642d772`，独立分支 `codex/llm-settings-v71-20261107`。按仓库 `docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md` 的 V7.1 规范调整界面，不修改模型配置、请求、权限或医学合同。

原页面使用独立侧栏、重复玻璃卡片和旧 `ds-*` 样式，角色配置又使用另一套固定宽度表单。调整为配置概览、编号连接的默认模型与用途分工、默认折叠的高级参数，以及底部操作栏。复用公共 `mq-card`、`mq-inset`、`mq-soft`、字段、按钮、状态及 token；去掉模型页父级卡片，避免玻璃卡片嵌套。角色设置随容器宽度换行，自定义模型管理折叠展示。

## 行为保留

- `LLMApiConfig.vue`、`LLMTaskRoleSettings.vue` 的完整 script 与基线逐字一致。
- 保留云端／本地模型、角色继承、目录加载、参数边界和原操作处理函数。
- 保留本地服务未就绪提示与角色配置完整性提示。
- 保存、恢复默认、连接测试的权限、禁用和加载条件沿用原实现；本次浏览器走查未点击这些操作。
- 不改后端、共享主题、迁移或相邻设置页。回滚本次 Vue 改动即可恢复旧界面，无数据库变更。

## 必要验证

在 `apps/medqc-web` 执行：

```powershell
node --require ./scripts/frontpage-v2-no-network.cjs node_modules/vitest/vitest.mjs run tests/unit/components/LLMApiConfigStrata.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts --maxWorkers=1 --minWorkers=1
node node_modules/eslint/bin/eslint.js src/components/LLMApiConfig.vue src/components/LLMTaskRoleSettings.vue --no-fix --max-warnings 0
```

结果：19 项通过；两组件 lint 零错误、零警告。用仅包含两组件及声明文件的临时配置执行 `vue-tsc --noEmit`，通过。父页面仅更换模型标签页容器 class；其 62 条既有格式警告与基线逐条相同，无新增错误或警告。`git diff --check` 通过。

当前浏览器实际 CSS 宽度 1441、1180、737 下均无横向溢出；参数区可展开／收起，玻璃卡片嵌套数为零，临时视口覆盖已恢复。当前本机页面已热更新，未保存配置、连接模型或执行质控；自动任务继续关闭。

本轮不重复全量前端测试、后端质量门或构建；不把界面验证称为真实模型及完整业务验收。未推送、合并或部署。
