# 已保存结果反馈的来源准入修复

本地请求日志显示，任务详情、latest-result、文书接口均为 200；
GET /api/v1/qc/sichuan/workspace/result-feedback-demo 返回 clinical_source_disabled。
该入口只按 root_job_id、record_ref、固定演示集合归属读取已保存反馈，
不读取当前 CDM，却被全局来源选择要求启用当前来源。

将这个精确 GET 路径纳入业务元数据读取边界；保持原登录、演示反馈角色、
Canonical 记录关联和集合归属校验。非法来源及冲突来源仍拒绝。
不豁免会调用 collect_records 的 /all 汇总入口，不豁免 PUT 或相似路径。

新增请求级隔离测试与既有反馈测试共 30 passed；修复前新增用例 3 failed / 5 passed。
Ruff F、git diff --check 通过。仅使用合成反馈和离线 runner，禁止网络/模型及非 SQLite 连接。
未改历史任务、结果、配置或权限；未运行质控、未连接服务器业务库、未合并或部署。
本地 API 按既有启动命令重启加载修复，后台恢复、巡检与调度继续关闭。
