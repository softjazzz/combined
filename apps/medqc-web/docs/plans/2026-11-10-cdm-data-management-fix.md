# 东华数据管理页面修复

基于50e0127d4，独立分支codex/cdm-record-view-20261110；没有修改后端权限、读取范围、模型或数据库。

## 已修复

- 按正式来源options选择已启用来源，每次读取携带来源身份；失败明确提示，不回退旧来源。
- 对接东华列表的instituteId/patientId/id及原旧字段，缺三坐标拒绝请求，不再生成undefined路径。详情请求编码路径参数，同号跨机构卡片使用完整身份键；迟到响应不覆盖新选择。
- 东华不调用schema/table-data旧接口，不提供整表数据弹窗；明确说明当前只提供病例资料浏览，未将其伪装成完整表管理能力。
- 移除固定SQLite和data/medqc.db文案、固定“已连接”状态；移除按病例数估算诊断/手术总量，改为“未统计”。
- HTTP错误不会被当作详情对象并显示“诊断0条”；刷新清除旧详情和统计。
- 字体只引用本机已安装字体，缺失则走既有系统字体栈；不请求客户包未包含的OTF。正式构建使用index.css，index.prebuilt.css为开发预构建样式，本轮未修改其生成内容。

## 验证

```text
node node_modules/vitest/vitest.mjs run tests/unit/views/workstation-v4/CDMDataView.source.spec.ts --maxWorkers=1 --minWorkers=1
node node_modules/eslint/bin/eslint.js src/views/workstation-v4/CDMDataView.vue tests/unit/views/workstation-v4/CDMDataView.source.spec.ts
```

4项页面挂载/API Mock保护通过，修前50e0127d4四项均失败。ESLint及diff检查通过。固定合成病例，无真实HTTP、业务库或模型调用。未跑全量、未构建或部署。前一提交14项结果未重复累加为本轮测试。

## 保留限制

业务助手access的503是另一条授权能力链；GlobalAssistantHost已捕获失败并隐藏入口，不阻断数据页面。没有现场响应正文，不能认定其具体配置缺口，更不能通过放宽授权或自动启用助手修复。此次未改助手后端。

页面仅展示接口返回的当前预览页，不代表全库数据或材料完整。东华整表结构浏览没有后端受支持接口，仍不开放；新增此能力需另行限定对象及权限。实际首页和文书内容仍需交付后的现场验收；本轮不宣称浏览器完整点击链、字体网络请求或模型质量已经现场通过。保留1026、旧冻结和历史结果。
