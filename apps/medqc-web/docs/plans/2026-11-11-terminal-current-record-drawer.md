# 终末/运行页：未质控也可查看当前病历

基线2b5c93003，独立分支codex/cdm-record-view-20261110。
用户确认终末页点击查看无法打开抽屉。原表格“查看”发出open-full，绑定handleOpenResult；not-run直接返回，导致没有质控结果也无法阅读已存在的CDM文书。

修复：紧凑列表明确区分“查看病历”和“查看结果”。查看病历通过完整recordKey匹配三坐标，打开独立ADrawer，复用QCRecordCompareWorkbench的documentOnly及sourceView=current；不传jobId，不读取质控结果作为文书前置。已有结果的行保留独立查看结果按钮及原结果权限链。身份不全拒绝；切换阶段/打开结果关闭当前阅读。无文书不代表合规。

验证：QcRecordResultListView 27项、QcRecordResultTable 14项通过；阅读组件QCRecordCompareWorkbench 31项通过（同一阅读组件未修改，复用本轮前一次定向运行）。共72个不同用例，不累加重复执行次数。新增运行/终末未质控用例检查实际按钮点击后抽屉内阅读组件身份、current模式、无jobId以及结果抽屉保持关闭。既有结果按钮及失败轮保护调整为点击明确的查看结果入口，未放宽结果校验。
ESLint定向0错误；既有样式/测试组件警告保留，新增按钮换行警告已修正。未跑全量、未构建或部署新前端，未连接业务库/模型、未重跑27份。

现场后端即时装配已由用户确认可用。本修复是新的前端源码，尚未进入已部署的eb2fbb4ca前端包。后续制包需以该已安装前端及现有receipt为基线，不可复用要求原始e1前端的首次安装脚本直接覆盖。
