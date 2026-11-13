# 失败任务详情入口修复

基线：3c790fc2d；独立分支 codex/failed-task-details-20261113。

## 行为

- 病历池终态任务增加“查看本次结果与失败原因”，进入 /workstation-v5/qc-task?job_id=本次任务ID。
- 任务入口复用现有授权任务 API，展示已保存的部分结果，不要求结果通知或结果信封。
- 原 qc-result?notification_id 入口不变；通知不存在时绝不把通知 ID 当任务 ID，也不读取最新任务代替。
- 查询失败、账号切换、任务切换和迟到响应不保留其他任务内容；导出、调试等既有操作前仍重新核对相应入口权限。
- 失败摘要展示保存数量、规则编号、受控错误码与阶段。后端客户投影仅增加已定义的模型/材料错误白名单与阶段，不回传原始异常、请求体、凭据或任意错误文本；未知原因明确保留为未知，不猜测供应商错误。
- 不更新历史任务、材料、信封或规则结论；无迁移、任务创建、重试或模型调用代码变更。

## 必要隔离验证

前端 Vitest（合成响应，使用已有 .tmp/pr59-ci.vitest.mts 依赖别名）：
- notificationQcResult.spec.ts：26 项，通知兼容、任务读取、部分结果原样传递、权限拒绝、未登录、账号切换、任务身份和迟到响应。
- RecordPoolQcTaskStatusBar.spec.ts：12 项，新增明确任务ID入口，既有进度与导出保护。
- BatchTaskFailureSummary.spec.ts：4 项，部分结果、材料失败、未知异常不回显、成功历史任务不显示失败提示。
- SemanticRulesBatchResultDrawer.spec.ts：46 项，部分结果与原抽屉保护。修正一条早已过时的“无补跑计划”文案断言；其余未知/矛盾计划断言保持不变。病历标识接口改为合成响应，隔离网络。

后端使用 scripts/run_pr8_offline_tests.py：禁 dotenv、网络和非 SQLite 连接，不加载应用 lifespan。
- test_failed_task_detail_projection.py：7 项，模型/材料错误白名单、未知字段脱敏、旧错误合同及输入不变。
- test_qc_material_admission.py::test_safe_failure_dto_no_raw_text：1 项，既有材料安全投影保护。
- test_failed_task_detail_access.py：3 项，实际 FastAPI 任务路由，未登录401、其他用户404、所属用户200；服务用合成内存替身，保留部分结果与错误码，数据不变。

开发过程先复现前端入口和后端错误码丢失，再修改至通过。一次旧共享池测试调用因隔离运行器不加载 client fixture 而未执行测试，后改用显式构造、无 lifespan 的上述接口测试；不把夹具错误计为产品失败或通过。

定向 ESLint：0 errors，存在旧文件格式 warnings；git diff --check 与 UTF-8/LF 检查通过。

## 限制

未跑全量、构建、真实浏览器、现场部署或模型；未连接业务库、CDM 或 Caché；未跑质控及27份材料。不能据此宣称现场页面已修好。旧记录未保存的供应商响应/HTTP错误细节不能由此次修复补造。
