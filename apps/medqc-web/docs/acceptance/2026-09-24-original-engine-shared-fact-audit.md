# LX0609 原始引擎阶段 D：共享恶性事实并发审计

## 范围与结论

本轮只审计原始规则 `LX0609-04-02-03`（手术族）与 `LX0609-08-01-04`（肿瘤病理族）的共享恶性事实。没有修改生产代码、模型参数、医学判据或规则结果。使用合成材料和固定模型响应直接并发执行两个真实规则族函数，不访问数据库或真实模型。

**确认的缺陷：**相同住院事件的两族在模型响应前同时进入 `MalignancyFactResolver.resolve()` 时，实际发起两次模型请求，而结果统计只认领一次调用和一次用量。当前 resolver 还把首次 `_resolution` 无条件交给后续调用，未按来源范围区分；只给现有缓存加锁会保留错误复用风险。

## 源码路径

1. `execution.py:423-445` 在一次原始引擎执行中创建一个 `MalignancyFactResolver` 并传给规则族资源；`engine.py:384-387` 为规则族创建并发任务。这是生产路径的静态调用链证据。
2. `native_surgery_gate_execution.py:2320-2345` 与 `native_tumor_pathology_execution.py:1743-1750` 都会对同一 resolver 调用 `resolve()`，随后各自调用 `claim_usage()`。
3. `malignancy_fact.py:325` 仅在进入 `resolve()` 时检查已完成的 `_resolution`；模型请求在 `:392` 的 `await` 处让出执行，响应后才在 `:397-403` 保存用量与结果。并发进入的两个调用因此都能到达模型。`:410-414` 的一次性 `claim_usage()` 只返回一份用量。
4. 同一文件 `:325` 也没有比较本次 `sources` 与缓存来源。两次请求若来源不同，后一调用仍可能直接获得第一次的结论。来源身份至少应覆盖来源键、实际行、完整性和用于阴性结论的要求。`available` 与 `present` 在已读取相同行时是同一资料的状态别名，不应单凭字面差异拆成两次语义请求；`error`、`unavailable`、`truncated` 等不能这样归并。

## 固定输入复现

`backend/tests/unit/test_luxian_0609_shared_malignancy_audit.py` 使用一份合成手术记录、诊断行和出院记录构造真实 `EvidenceReadSession`，并用屏障客户端使两族模型请求同时在途。断言读取的诊断来源键和行相同，来源状态分别是 `available`、`present`。

| 场景 | 客户端实际请求 | 两族合计归因 | 可见结果 |
| --- | ---: | ---: | --- |
| 有效固定响应 | 2 次，各报告 15 Token | 1 次、15 Token | 两族返回 |
| 无效固定响应 | 2 次，各报告 15 Token | 1 次、15 Token | 手术族 `model_transport_error`；肿瘤族 `executor_exception` |
| 请求在途时取消 | 2 次已进入客户端 | resolver 尚未认领用量 | 真实提供方是否计费未知 |

无效响应的原因码来自两个规则族现有状态映射，不能把测试期待的单一 `malignancy_llm_invalid` 当成交付原因码。取消实验只证明当前代码没有认领用量，**不能**证明提供方实际消耗为零。

测试命令：在 `backend/` 下设置合成 `JWT_SECRET`、空 `DATABASE_URL`，运行 `py -3.10 -m pytest --confcutdir=tests/unit -q tests/unit/test_luxian_0609_shared_malignancy_audit.py --disable-warnings --tb=short`，结果 **3 passed**。

这里的并发实验直接调用两个真实规则族函数；未通过完整 `Engine.run()` 与任务保存链。因此它证明共享 resolver 的执行行为，生产引擎会并发调度这些族由上述静态调用链支持；尚未证明真实客户病例发生频率、实际费用或整批任务耗时贡献。

## 后续最小修复与验收边界

先冻结同一请求内哪些来源可共享：实际来源键、行、完整性和阴性判定要求一致时共享；`available`/`present` 仅在资料等价时归一。不同来源范围必须分别判定，不能复用首个 `_resolution`。随后在 resolver 内为等价且同时在途的调用只创建一次请求，明确各规则族读取同一结果时由谁认领模型调用、Token 与 API 时间。取消一个等待者不能意外中断仍需结果的族；全部取消、异常和部分用量则按实际可观测数据记账，不编造为零。

固定相同输入与模型响应，对比修复前后的两族状态、原因码、证据、实际请求数和合计归因；补不同来源不共享、单等待者取消、全部取消及失败重试实验。最终还要走完整引擎与任务保存路径，并用有授权的真实病例验证。此报告只作为阶段 D 的实施依据，不是临床验收。
