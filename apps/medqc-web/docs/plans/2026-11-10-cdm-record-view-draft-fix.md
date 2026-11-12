# 东华病历查看误请求AI草稿修复

基线：e1f65ffe73f121842dfa997c41d1c9c517bd804e。
分支：codex/cdm-record-view-20261110。

## 原因及改动

useFrontpageDraft只监听visit号，选中东华病例也请求旧AI草稿接口。后端按独立CDM只读边界拒绝422；该异常已捕获，不能仅凭此认定正文加载也失败。相同visit号切换来源未重新清理，延迟返回还可能覆盖新病例草稿。

现在按来源、机构、患者、就诊与选中号共同监听。东华病例、病例尚未加载或选中号与病例不一致时不请求草稿；开始加载先清空旧状态，异步成功和失败返回都检查当前身份和请求序号。旧来源已有草稿和空草稿行为保留。后端拒绝规则未放宽，未新增旧库回退。

原始首页、文书目录和EMR正文读取链未修改。本轮不开放东华AI生成/保存功能。

## 必要隔离验证

在apps/medqc-web执行：

```text
node node_modules/vitest/vitest.mjs run tests/unit/views/workstation-v4/useFrontpageDraft.source.spec.ts tests/unit/clinicalSources.spec.ts tests/unit/views/workstation-v4/RecordDetailWorkspace.panel.spec.ts --maxWorkers=1 --minWorkers=1
node node_modules/eslint/bin/eslint.js src/views/workstation-v4/composables/useFrontpageDraft.ts tests/unit/views/workstation-v4/useFrontpageDraft.source.spec.ts tests/unit/views/workstation-v4/RecordDetailWorkspace.panel.spec.ts
```

实际分批执行上述三个文件，最终对应6+5+3=14项通过，ESLint通过。初始草稿保护5项在修改前4失败、1通过；修后通过，随后增加身份尚未同步对照也通过。组件新增测试首次因异步组件查找夹具不正确失败，改用明确查看器stub后通过，不计产品缺陷。

所有API均为Mock，没有真实HTTP、业务库、模型或质控任务。组件测试证明无草稿也挂载原文查看器并传递三坐标，不等于实际EMR正文请求、渲染和浏览器完整点击链已现场通过。未跑全量、完整类型检查、构建或远端CI。

## 交付后现场核对

部署需另行授权。点击东华病例应不再发起ai-frontpage-draft请求；确认实际EMR documents/render及原始首页请求成功、正文可见。若仍为空，记录具体失败接口和脱敏错误码继续定位，不把草稿422消失等同所有正文问题解决。切换病例不得残留旧草稿。保留1026材料、历史结果及旧冻结；本轮未推送、合并、打包或部署。
