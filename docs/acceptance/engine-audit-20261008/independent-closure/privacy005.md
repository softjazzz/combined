# PRIV005 固定提交独立复审

结论：在本次明确的 0609 HTTP 上游错误摘要与 snapshot 异常日志边界内，未发现新增可确认缺陷。独立冻结的 15 项标准库探针全部通过；完成层级为固定源码静态复核和函数消费边界验证，不能据此宣称全工程、客户链或部署通过。PRIV002 原身份来源问题仍开放。

审阅对象为 `041b3be67a9e34df7c0d72ce83e0c53c0d89687a`，父提交为 `6930540f27e9c279241d35ac05d1c1c6e9134f82`。生产源码均来自 `git show` 固定提交，未混读 privacy 工作树的后续 PRIV004 修改。0916 排除于本次验收。

## 源码与消费路径

- `apps/medqc-web/backend/app/services/qc_llm_client.py:445`：0609 scope 内只输出固定前缀、安全 HTTP 状态和白名单枚举；未知、非字符串或白名单相似的 code 回落为 `upstream_response_error`。正文、message、request_id、provider/model/endpoint 均不拼入该异常，使用 `from None`。非 0609 分支保留父提交逻辑。
- 同文件 `generate` 的初次调用及长度重试在 transport 返回后调用 `_raise_for_upstream_error`；异常仍更新调用错误统计并上抛。`_perform_observed_attempt` 在 transport 前执行隐私闸门。诊断捕获仍接收原响应，现有契约为明确授权的私有内存诊断；本次结果不证明诊断实现或其他日志接收端无泄漏。
- `apps/medqc-web/backend/app/services/luxian_0609/execution.py:362`：snapshot 捕获由 `logger.exception` 改为固定 `logger.error`，不设置 `exc_info`。捕获后继续将 snapshot 构建失败状态交给身份 provider 边界，未改变异常旁路控制流。
- 正式调用的 scope 由 `running_final_bundle_service.evaluate_running_final_bundle_input` 与 `sichuan_qc_service._evaluate_rules_orchestrated` 建立；内部空规则集继承上下文。该独立探针没有执行全部正式 worker/API 链路。

## 独立冻结与观测

`expectations.json` 在探针执行前冻结 11 个 HTTP 反例及边界期望，其 SHA256 为 `aaef4df8c5fc65bf8564ccfa900456932e87f11add272037be49ce7eb50c3507`。反例覆盖字符串/列表正文、顶层及嵌套未知 code、code 类型异常、私密字符串/布尔/越界状态、嵌套 type 回落、白名单枚举和枚举相似字符串。全部标记均为合成值。

`probe.py` 从固定源码 AST 加载完整客户端类，以真实 `generate → _perform_observed_attempt → _raise_for_upstream_error` 方法体消费合成响应；再加载完整 `prepare_luxian_0609_execution` 函数，使 snapshot 构建抛出合成异常，执行实际捕获分支，并在身份 provider 边界停止。transport、配置、观测、库存与 snapshot 来源均为内存替身。纯隐私 scope 模块按固定文件完整加载。

执行命令：`python -B F:/MedQC-worktrees/review-artifacts/privacy005/probe.py`。结果见 `results.json`：15 passed / 0 failed，探针主逻辑约 0.016 秒。11 个反例在父提交均可观察到合成标记，在固定提交均只能得到预期安全异常；另外验证非 0609 异常与父提交一致、共享客户端并发 scope 隔离及退出恢复、snapshot 日志无 traceback 且失败状态传播、消费路径错误统计及替身观测元数据。未使用 pytest、PG、真实模型、服务、浏览器或 `.env`，未编辑生产源码。

## 既有测试覆盖与仍缺门禁

提交新增 `test_scoped_errors.py` 的 8 个用例覆盖错误格式化方法、scope、非 0609 兼容及日志字段；snapshot 用例只提取 except-handler 的 AST。它们能支持这些局部断言，不能证明真实 `generate` 或完整 `prepare` 已消费该修复。本次独立探针补充了这两个方法体的消费边界，但配置、导入、数据库、完整观测和下游引擎均使用替身，仍不是完整模块应用验证。

仍需在最终集成 SHA 重跑受控工程测试及正式任务/API/worker/保存/读取/导出链，并审计实际日志/观测接收端。客户安装、模型连接、权限和部署门禁不在本次执行范围。005 原提交缺少本地 `.husky/_` 的事实保留，本报告不宣称其历史 Husky 钩子通过；后续补齐应关联新证据。004 的钩子证据不能追溯替代 005 的历史事实。

## 产物索引

- `expectations.json`：冻结反例与边界。
- `probe.py`：独立标准库消费探针。
- `results.json`：逐项观测与固定 SHA。
- `qc_llm_client.fixed.py`、`qc_llm_client.baseline.py`、`privacy_request_scope.fixed.py`、`llm_prompt_privacy.fixed.py`、`execution.fixed.py`：不可变 git-show 源码副本。

可确认 findings / defects：空。上述未执行门禁为验证限制，不等价于已发现产品缺陷或部署通过。
