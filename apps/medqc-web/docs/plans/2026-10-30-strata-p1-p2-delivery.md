# Strata P1与最小P2交付记录

日期：2026-10-30。开发基线 `467af4e78264358e03271921600e9ffaeb510a10`。
工作树 `C:/medqc-strata-case-cache-20261030`，分支 `codex/strata-case-cache-20261030`。
实施合同见 `2026-10-30-strata-p1-p2-contract.md`；本文覆盖此前P0文档中“prefix尚不可用”的历史状态。

## 完成内容

1. Gateway增加可选 `case_prefix` 协议和有界、短期checkpoint元数据；仅支持Strata，不持久化患者正文或远端KV。
2. Prime与规则请求均走原有准入、lease、截止时间和故障隔离。资源仍为配置的2槽；等待同一Prime不占模型槽位，但参与者总数受资源槽位加队列容量约束。
3. 缓存键绑定病例、最终脱敏材料、上下文/schema、规则集版本、角色、真实模型/profile/resource、部署及模板身份。TTL、容量、取消、超时和重启保持可回退。
4. 只适配 `exam_result_record_check.py::_check_result_batch` 的原请求及补核证据组。Worker保留单user原文，实际命中缓存路径时Gateway才分为完整证据和完整指令两条user消息；不改事件、候选、输出schema或判定代码。
5. Prime独立计入请求、Token、Prefill、Decode、排队、传输和墙钟观测；缺失/非法字段保持未知。规则墙钟已含Prime，不重复相加。
6. 已成功的规则应答不会因为缓存miss被重问；Prime失败不制造临床合规。Provider不能伪造Gateway成本trace。

## 默认与最小闭环边界

Worker默认 `STRATA_CASE_CACHE_MODE=off`，另支持 `observe` 和 `prefix`；不支持亲和模式。
Gateway默认 `STRATA_CASE_CACHE_ENABLED=false`。启用须显式提供安全的
`STRATA_CASE_CACHE_DEPLOYMENT_VERSION`；TTL默认60秒，元数据上限默认64。
没有修改任何运行环境文件或启用中的服务。

普通核验调用预算为1，不把“可能重试”当成两次已知请求。因此冷状态的普通核验仍直接发送原payload，不自动Prime。
已有checkpoint可直接复用；明确计划多次调用的调度方可使用
`exam_result_prefix_scope(expected_requests=2)`，预算随提交消耗为 `[2,1,1]`，不会被内部作用域重置。
这是显式计划→Prime→原核验→补核复用的最小闭环，不代表普通核验现在已自动提速。

Prime最低证据长度为1024字符，是保守跳过短输入的门槛，不是Token计数，也不证明净收益。
旧临床usage/UI Token汇总保持原语义；包含Prime的总成本在新增观测collector中，不能将旧UI数字声称为完整推理成本。

回滚时在请求排空后恢复Worker `off`、Gateway缓存开关 `false`，不删除故障隔离标记，也不改成功结果。

## 隔离验证

统一运行：`py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-prefix`，
同时追加下列24个已有保护文件；实际结果 **719 passed，70 warnings，42.90秒**。
这是一次统一运行，未与子代理各自测试数字相加。

```text
test_shared_http_client.py
test_luxian_0609_task_runtime_identity.py
test_failed_rule_retry.py
test_qc_sichuan_batch_cancel.py
test_latest_full_record_result.py
test_luxian_0609_record_result_read_model.py
test_qc_sichuan_record_result_exports.py
test_qc_execution_timing.py
test_record_execution_timing.py
test_luxian_0609_canonical_result_finalizer.py
test_luxian_0609_execution_privacy_identity.py
test_luxian_0609_privacy_request_scope.py
test_luxian_0609_production_extension_boundary.py
test_luxian_0609_059_shadow_execution.py
test_luxian_0609_native_treatment_order_consistency.py
test_qc_llm_client.py
test_qc_llm_client_thinking_budget.py
test_qc_llm_client_qwen_thinking.py
test_llm_observability_independent_egress.py
test_llm_gateway_api.py
test_llm_gateway_admission.py
test_llm_gateway_cancellation.py
test_luxian_0609_exam_result_record_check.py
test_luxian_0609_native_exam_lab_execution.py
```

追加文件位于 `tests/unit/`。suite定义在 `scripts/run_qc_scheduler_tests.py`，沿用禁止dotenv、真实网络/数据库和普通子进程的offline护栏；只使用合成材料、MockTransport、进程内ASGI及内存SQLite。

覆盖单Prime与两次规则请求、并发singleflight、资源级等待上限、取消释放、TTL/版本隔离、坏L0、已知失败冷回退、未知远端状态隔离、缓存miss成功不重问、成本未知和Provider伪造trace。
实际检查核验→应用事实→Native→Binding→Finalizer→Canonical内存SQLite保存读取，对照off/prefix的状态、原因、事实、证据及文案完全相同。
非法引句、超声混作CT及原有任务恢复、选轮、导出、隐私边界保护通过。

复审修复：singleflight等待者资源总量原先无界，现受容量限制；Prime截止超时原先可产生不一致trace，现明确为 `prime_failed` 并保留成本未知。

相关Python Ruff通过；核验文件仅豁免HEAD已有且未改动的E731 lambda，未全局关闭检查。
暂存21个文本文件通过 `npm run check:encoding`、UTF-8无BOM/LF及Python3.10 AST检查。
无前端代码、迁移或依赖变动；未运行前端完整类型/单测。实际执行 `npm run lint -- --no-fix`，因本工作树未安装eslint失败，不能宣称通过。
本机Python3.10.11、HTTPX0.28.1、Pydantic2.13.4；未以锁定依赖重建环境或运行远端CI。
70项警告包括FastAPI/Pydantic弃用及本机NumPy/SciPy版本警告，测试未失败。

## 未实施与未证明

未做亲和调度、其他规则族适配、整个病例材料拼接、RabbitMQ行为改造或医学合同变更。
没有连接客户机、Strata或真实模型，没有访问新患者资料、写业务库、运行质控或移动业务集成分支。
固定应答能证明协议和结果搬运一致，不能证明现场Token checkpoint边界、模型输出等价、GPU性能、命中率、净成本或完整病历吞吐；这些仍需后续单独授权的现场验收。
