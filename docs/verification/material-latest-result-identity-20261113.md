# 1026 最新结果入口身份兼容

## 根因与修改

`GET /api/v1/qc/sichuan/workspace/records/{record_id}/latest-result` 的路由明确将
`record_id` 作为就诊号传给结果仓储，但来源准入只读取 `visit_id`，导致 PDF 材料身份不完整。
仅对该 GET 路由将路径身份归一化；显式 visit_id 冲突仍拒绝。
机构、患者、就诊三坐标仍须命中原材料登记，不改变鉴权、来源隔离或历史结果完整性校验。
不为其它 record_id 路由猜测身份，不修改任务、快照或结果。

## 隔离验证

新增 6 个合成用例：合法登记、就诊冲突、缺机构、缺患者、跨机构未登记、其它路由禁止推断。
修复前 2 failed / 4 passed，修复后通过。
与既有来源定向回归合计 23 passed / 1 deselected。
排除项 `test_canonical_latest_same_keys_selects_only_matching_source` 首次执行在夹具构造
`_batch_jobs_table` 时因离线 runner 未设置 workspace.engine 失败，未进入业务断言；
未修改该夹具或关闭任何 CI 门禁，不将此项计为通过。
Ruff F 与 git diff --check 通过。

测试使用禁 dotenv、禁网络、禁非 SQLite 连接的离线 runner，仅合成材料登记。
未重启本地后端、未连接服务器业务库、未调用模型、未运行质控、未合并或部署。
当前运行中的本地后端需要后续重启才能加载本修复及前一项历史合同兼容修复。
