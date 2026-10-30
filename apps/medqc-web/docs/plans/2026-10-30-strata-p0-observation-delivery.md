# Strata P0 观测与请求组盘点

日期：2026-10-30。工作树 `C:/medqc-strata-case-cache-20261030`，分支
`codex/strata-case-cache-20261030`，开发基线 `af914704f`。

本轮完成 P0：补指标、准确区分请求与传输次数、盘点精确相同输入及候选证据组。
没有改 Prompt、建立 checkpoint、发送 Prime、增加规则合并或病例亲和调度。
没有访问客户机/Strata、调用真实模型、读取新增患者材料、写业务 PG 或改集成分支。

## 1. 使用与数据出口

新增 `STRATA_CASE_CACHE_MODE=off|observe`，默认 `off`。只有显式 Strata 客户端在
`observe` 时输出安全旁路观测。模式在客户端构造时读取，变更后需重新构造客户端或
按正常流程重启应用；本轮没有修改任何运行中的配置或重启服务。

其他 Provider 无新增专用请求字段和观测事件；`prefix` / `prefix_affinity` 尚未实现，
配置这些值会明确失败，不能把 P0 当成缓存已启用。

观测复用 `LLMObservabilityRecorder`，按现有 event_id、logical_call_id、attempt_no、
匿名病例键、executor 和模型角色关联。新增事件是 `strata_p0_attempt` 的 INFO 级结构化
日志，需部署日志级别允许该 logger。没有为本功能扩业务表或新增迁移，**P0 无需 PG 升级**。

生产默认不在进程里积攒全部请求。显式 `capture_strata_observations` 可在诊断作用域
收集有界的安全元数据，默认最多 1000 条、最大可配 10000；超限明确报告 dropped 和
complete=false。作用域结束后不污染其他任务，不保留 Prompt 或响应正文。

## 2. 指标口径

| 输出 | 来源与边界 |
| --- | --- |
| nominal_input_tokens | usage.prompt_tokens，名义输入量，包含可能复用的部分 |
| cache_tokens_usage / cache_tokens_timing | 分别保留 cached_tokens 与 cache_n，冲突时 cached_tokens=unknown |
| prefill_tokens | 只取 timings.prompt_n，不用 nominal-cached 推算 |
| prefill_ms / decode_ms | 分别取 prompt_ms / predicted_ms；不是应用墙钟 |
| output_tokens | completion_tokens / predicted_n，冲突保留原来源但合计量未知 |
| queue_ms / transport_ms | Gateway 取已有 queue_seconds/http_seconds；direct 在线程池及共享槽位实际获取后计时 |
| wall_ms | 单次客户端 attempt 的等待与传输墙钟，不把重叠的 Prefill/Decode/HTTP 再相加 |
| model_requests_started | direct 实际 client.post 次数；Gateway 成功 timing 对应当前无内部重试的一次 sender；无法证明时 unknown |
| unknown_usage_request_count | 已发出的请求中，未获可用 Token 成本的次数；不是零 Token |
| cache_state / cache_invalidation | 只报告 hit/miss 或 unknown；不把 cache_n=0 推断为确定淘汰，失效原因保持 unknown |
| token_accounting_delta | 仅显示不同计数的差额，不自动修正 read 或 cached |

负数、布尔值、字符串数值、NaN/Inf、溢出或缺失为 unknown。指标解析或候选分组失败
不会改变响应、补问、触发模型重试或产生医学结论。分组失败时仍保留已知耗时与 Token。

成本按请求、Token、阶段耗时记录；没有本地电力/设备价格，货币费用为 unknown，不能
把本地推理写成免费。所有总和有 unknown_count；失败请求、已有 length retry 都算
attempt。并行 attempt 墙钟之和不等于整批墙钟，报告明确分列 collection_wall_ms。
known_sum仅是已知条目的和；存在unknown_count、数值溢出或cost_complete=false时，
不能把该和当作完整成本（全部未知时的已知和0也不是“成本为0”）。

额外核实了 direct 路径既有“未收到响应即断开”重发一次：本轮没有改变此策略，只
记录其两次发送和第一条未知 usage，避免最后一条成功响应掩盖全部成本。取消阻塞 HTTP
等待时，仍在运行的后台请求显示 transport_complete=false，不假装远端已结束。
此时发送次数是观测瞬间已开始的次数，不能当作最终总量；报告 pending_transport_attempts
与 cost_complete=false。complete 仅表示有界事件集合未截断，不表示病历或任务成功完成。

P0 没有 Prime 路径，因此本作用域 prime_requests_started=0；未来启用 Prime 必须升级
该合同并将其显式计费，不能通过 max_tokens=1 猜测某次请求是不是 Prime。

## 3. 精确分组与合成材料证据

分组只读取最终隐私保护后的消息。使用现有匿名病例域及 HMAC 摘要，绑定当前任务/
规则集版本、模型、模板参数、响应格式及路由身份。没有病例归属、不支持的消息形状、
超过 32 条消息或 262144 字符时，不生成共享组；不会截断后把不同输入当成相同输入。

三种输出不可混用：

1. `input_group_key`：完全相同的输入消息/模板；表示重复输入，不证明远端缓存仍在。
2. `leading_messages_key`：最后一条消息之前的完整相同消息候选。当前单 user Prompt
   没有这样的消息边界；不把公共字符片段伪装成 Token checkpoint。
3. `evidence_projection_key`：只对已核对的检查专项生产者，盘点末尾 EVENTS_JSON 原始
   字节。不会排序或修复 JSON、拆消息、重排材料或创建 PrefixPlan；仍是 P1/P2 候选。

严格隔离探针使用真实 Prompt 生产函数、真实 client/Gateway 与 MockTransport，
7 次合成请求覆盖：报告结果核验原请求、故意重复输入对照、真实补核 Prompt 生产者、
结果分析的另一投影、不同候选范围、原生主抽取、同正文的另一病例。

| 发现 | 证据和限制 |
| --- | --- |
| 一组完全相同输入，2次 | 第二次是刻意设置的重复对照，不能据此断言生产执行存在冗余调用 |
| 一组相同证据 JSON，3次 | 包括上述原请求/重复对照和一次真实补核生产者；补核的完整 Prompt 不同，不是现成的相同 Token 前缀 |
| 现有完整消息头候选为0 | 7次均为单 user 消息；不能只加 strata_prefix 就宣称共享完整病例 |
| 结果分析与报告记录核验不共组 | 前者使用片段投影，不能因为同一患者或同一报告就合并输入 |
| 缩小事件候选范围后不同组 | 裁剪和可见证据范围变化保持可见，不为提速拼成全量材料 |
| 同文本的另一病例不共组 | 病例归属域参与身份，即使正文完全一致也不会混组 |

这些是合成材料上的请求形状证据，**没有验证 Strata Token 命中或生产节省比例**。
探针的 Token/Prefill/Decode 数值全部是明示的固定夹具，不是 GPU 测量。

## 4. 11族来源盘点与适配边界

统一入口为 `luxian_0609/execution.py::prepare_luxian_0609_execution`，注册顺序在
`executor_registry.py::LEGACY_NATIVE_EXECUTION_ORDER`。下面是源码边界盘点，不是
11族真实病历运行轨迹或每例模型调用数；实际是否调用受选项、分批、门控、补核、预算
和事实冻结影响，不能把规则数当调用数。

| executor | 当前主要输入/所有者 | P0结论 |
| --- | --- | --- |
| surgery_presence | native_execution，同一证据会话的手术记录存在性入口 | 此入口无 llm_client，不创建虚构的模型缓存机会 |
| basic_timeliness | native_basic_timeliness，确定性时间；抢救完整性另接语义抽取 | 不能把整个族都算成零调用；只统计真正到达客户端的请求 |
| exam_lab | exam_lab_fact_extraction及三个专项核验，各自事件目录/病程投影 | 本轮已作上述合成分组证据；片段和完整正文不共组 |
| consultation_quality | native_consultation_episode_execution，意见与执行证据分阶段 | 阶段/候选范围不同不能直接共享全前缀，等待实际 observe 元数据 |
| transfusion | native_transfusion_execution及抽取模块，输血事件、专门评估评价和医嘱分批 | 前评估、后评价、医嘱语义不是同一材料组，不改已有两批并行 |
| tumor_pathology | native_tumor_pathology_execution，病理/肿瘤门控与内容投影 | 门控事实复用和 KV 复用分别计量，不把已冻结事实当作 cache_n |
| course_quality | native_course_quality_execution及course_quality子模块，首程/查房等范围 | 时间窗、裁剪、问题均可能不同，按实际相同输入盘点 |
| surgery_gate | native_surgery_gate_execution，术前材料与身份/资格相关投影 | 不追加其他族可见的材料来制造共同前缀 |
| surgery_document | native_surgery_document_execution，围手术文书与限制后的上下文 | 现有裁剪上限保留，不能沿用另一个族的前缀 |
| surgery_mdt | native_mdt_execution，讨论/人员和手术资料投影 | 窄材料请求不应为了全例缓存扩大输入 |
| extended_document | native_extended_document_execution及extended_document各抽取模块 | 多子组独立，不能视作一个固定长病例 Prompt |

`unified_rule_engine.py::evaluate_batch_compact/_build_batch_prompt_compact` 是单独的既有
打包路径：规则卡片在前，证据预算和投影可变化。不能用它的合成对照替代 native 11族
的覆盖，也不在本轮改变 3–15 条规则等既有打包粒度。

`qc_execution_cache.py` 的结果 TTL 与 `luxian_0609/*freeze.py` 的已校验事实冻结保持
原样。缓存命中可能使某次根本不发 HTTP；本报告只计已观测 attempt，不能据缺少事件
推断没有选中规则或零整体成本。现场要并列保留这两层命中信息。

## 5. 复现与验证

在 `C:/medqc-strata-case-cache-20261030/apps/medqc-web/backend`：

```powershell
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-p0
py -3.10 scripts/audit_strata_p0.py --output .tmp/strata-p0-synthetic-report.json
```

第一个入口禁 dotenv、真实网络、非合成数据库和普通子进程；第二个独立入口同样先安装
OfflineIsolation，只有固定合成输入与进程内 ASGI/MockTransport，无任意服务地址参数。
报告只写安全元数据；原始 Prompt 和响应正文不写入报告。

- 开发中P0聚焦：58 passed，1 warning，2.79秒。含默认关闭/非Strata兼容、精确请求不变、
  缺失/冲突/异常指标、分组失败、断连内部重发、取消在途、并发病例隔离和实际Gateway。
- 扩大兼容保护：364 passed，72 warnings，21.81秒。覆盖结果保存/选轮、隐私、预算、
  旧客户端思考/length retry、共享HTTP、Gateway准入/取消/错误路径；与P0有重叠，不相加。
- **最终统一保护：423 passed，70 warnings，56.83秒**。在 strata-p0 上追加下列22个
  相邻文件，包含最后增加的数值聚合溢出与取消在途成本反例；以前面的最终统一结果为准，
  开发过程的58/364不与423相加。
- 合成探针：7次固定应答、真实模型调用0、Strata连接0、业务数据库写入0，未运行病历质控。
- 修改Python的Ruff、Python3.10 AST、UTF8无BOM/LF与diff检查作为提交前门禁。
- 前端没有修改。尝试只读 `npm run lint -- --no-fix`，本工作树缺少eslint依赖，未通过环境
  前置检查；不安装整套前端依赖或修改无关页面来凑绿。全量前端类型/单测未运行，不能记通过。
- 没有执行客户环境、真实模型、性能压力或GPU测试，也没有验证缓存收益/医学准确率。
- 本机使用Python 3.10.11、HTTPX 0.28.1、Pydantic 2.13.4；未推送，未运行锁定依赖的
  Linux CI，不能把前一M2提交的CI结果冒充本次P0结果。

后续P1/P2应先解决这一组“证据相同、指令不同”的明确适配候选，并作消息边界和医学
合同对照；不能根据本轮7次夹具值承诺整例Prefill、P95或病例/小时的改善。

最终统一保护复现：

```powershell
$qcP0CompatibilityTests = @(
    'tests/unit/test_shared_http_client.py'
    'tests/unit/test_luxian_0609_task_runtime_identity.py'
    'tests/unit/test_failed_rule_retry.py'
    'tests/unit/test_qc_sichuan_batch_cancel.py'
    'tests/unit/test_latest_full_record_result.py'
    'tests/unit/test_luxian_0609_record_result_read_model.py'
    'tests/unit/test_qc_sichuan_record_result_exports.py'
    'tests/unit/test_qc_execution_timing.py'
    'tests/unit/test_record_execution_timing.py'
    'tests/unit/test_luxian_0609_canonical_result_finalizer.py'
    'tests/unit/test_luxian_0609_execution_privacy_identity.py'
    'tests/unit/test_luxian_0609_privacy_request_scope.py'
    'tests/unit/test_luxian_0609_production_extension_boundary.py'
    'tests/unit/test_luxian_0609_059_shadow_execution.py'
    'tests/unit/test_luxian_0609_native_treatment_order_consistency.py'
    'tests/unit/test_qc_llm_client.py'
    'tests/unit/test_qc_llm_client_thinking_budget.py'
    'tests/unit/test_qc_llm_client_qwen_thinking.py'
    'tests/unit/test_llm_observability_independent_egress.py'
    'tests/unit/test_llm_gateway_api.py'
    'tests/unit/test_llm_gateway_admission.py'
    'tests/unit/test_llm_gateway_cancellation.py'
)
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-p0 @qcP0CompatibilityTests
```
