# 05-01-03 与 03-01-04 失败恢复正式修复

后续已完成本机真实快照三轮复验与受控漏项验证，并收尾旧测试断言及稀疏检出文件问题：完整零模型门禁 10,250 项全部通过。详见[后续真实复验记录](2026-10-15-failed-rule-recovery-real-validation.md)。下文保留首次修复阶段的验证结果和当时边界。

## 范围与实现

在 `C:\medqc-agent-merge` 的 `codex/business-agent-integration` 落地已验收的 [POC](2026-10-15-failed-rule-recovery-poc.md)，基线为 `613f55a58`。本轮没有构建交付包、更新客户机或调用真实模型。

### 05-01-03：逐配对核验与有限补齐

- 程序先固定文书与目标药物的配对及原始索引，模型输入明确列出 `requested_pairs`。
- 首轮逐项使用原有状态、原文引文及药物归属校验；通过项保留。第二轮仅发送未核验配对及相关文书、药物，不重新编号，范围外回答不能覆盖已采信事实。
- 重复配对、伪造引文和漏项仍不能通过；漏项不转换为 `absent`。有效的 `unknown` 继续按已有判定链处理，不凭空补为阴性事实。
- 每次规则执行最多两次逻辑抽取调用，底层已有的网络重试策略不变。仍有未核验项时返回技术失败及内部未解决配对，不把部分事实交给临床判定；该规则不再触发外层整条规则自动重跑。用户明确发起的手动重试仍保留。
- 两次已返回响应的调用数、Token 和耗时累加；没有上游用量回执的异常无法重建真实计费用量。合同调用上限同步为 2，合同版本为 v3；事实响应结构保持 v2，提示词版本更新。

### 03-01-04：按调用阶段区分失败

- HTTP 超时、连接失败、429、5xx、其他 4xx、JSON 解析、响应协议、配置及程序异常分别使用受控原因码，不再全部记为网络失败。
- 保留原有有界重试；429 与超时、连接、5xx 一样视为瞬时故障。协议、解析、配置及程序错误停止外层自动整条重跑。
- 第一阶段载入、调用、响应核验及冻结，以及第二阶段调用和核验，均记录所属阶段和代码位置。已有“语义核对未解决则资料不足”的行为保留。
- 日志只记录规则、阶段、类别、异常类、文件/函数和行号，或配对覆盖数量；不记录异常文字、请求地址、响应、病历正文或凭据。

### 混合失败的任务恢复

自动补跑范围只选择仍允许自动重试的“病历＋规则”；保留停止自动重试的失败明细及已成功结果。没有可自动补跑项时不退回整批重跑。恢复数量按本次实际补跑范围计算。手动补跑仍可选全部失败配对。

执行器负责事实和失败状态；保存层没有新增临床重判或放宽交付合同。

## 验证

全部使用脚本化模型客户端、合成文书及隔离 SQLite。真实模型调用 0，客户业务库连接与写入 0。

- 配对补齐反例先红后绿：原实现三个用例失败；最终核心定向、规则家族、合同、会诊核验及结果保存集共 900 项通过。
- 新增正式原生执行链两个用例通过：补齐成功后继续原有临床判定；补齐仍失败时保留技术失败，两次调用及用量均正确累计。
- SQLite 持久化用例验证：混合失败只补瞬时错误，其他失败与成功结果保留；全部停止自动重试时不启动整批重跑。
- 合成异常注入覆盖超时、连接、429、503、401、配置、JSON、协议及程序异常，并验证模拟秘密不进入日志。
- 门禁复查中修正两处兼容问题：只对能构造精确失败范围的任务过滤自动补跑，旧任务原有恢复路径保留；异常分类使用现有 HTTP 客户端依赖，避免新增依赖破坏离线网络哨兵下的回放导入。最终恢复边界、SQLite 持久化、异常分类和独立子进程会诊回放共 90 项通过（与 900 项有重叠）。

复现定向验证（在 `apps/medqc-web/backend`，`DATABASE_URL=sqlite:///:memory:`、`DB_SCHEMA_MODE=single`、`PYTHONUTF8=1`、`JWT_SECRET` 使用测试值）：

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_antimicrobial_effect_extraction.py tests/unit/test_luxian_0609_model_failure.py tests/unit/test_failed_rule_retry.py tests/unit/test_luxian_0609_native_consultation_episode_execution.py
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py tests/unit/test_luxian_0609_consultation_measure_check.py tests/unit/test_luxian_0609_consultation_public_boundary.py tests/unit/test_qc_partial_failure_persistence.py tests/unit/test_luxian_0609_rule_contracts.py
py -3.10 scripts/run_luxian_0609_quality_gate.py --profile pr-no-model
```

### 完整检查及基线核对

`pr-no-model` 首次完整运行：10,217 项通过，32 项失败/错误。合同组 814、原生执行器组 1,401、主链汇总组 651 全部通过；扩展组未通过。该结果不能写成全量门禁通过，也未修改或绕过门禁。

扩展失败提取后，修复本轮新增的三个失败用例（旧任务自动恢复一项、会诊独立子进程回放两项）。最终对剩余失败逐项比较：当前代码为 12 失败、3 通过、1 个收集错误；未落地本轮修复的独立 POC 工作树为同样的 12 失败、2 通过、1 个收集错误（未选择当前已修好的旧任务恢复用例）。失败标识完全一致：

- `test_luxian_0609_original_005_006_public_boundary.py` 六项、`test_luxian_0609_failure_usage_observation.py` 一项、`test_luxian_0609_production_extension_boundary.py` 两项、`test_luxian_0609_preproduction_benchmark20.py` 三项：旧 006 身份/异步接口/调用量及确定性规则数量断言未同步此前客户口径修复。
- `test_luxian_0609_effect_semantic_execution.py` 的收集依赖仓库根目录 `docs/acceptance/engine-audit-20261008/phase3-050055-expectations.json`，该文件不存在。并行门禁中同一问题被 14 个 worker 各记一次收集错误；没有补造预期文件或跳过测试。

首次并行失败中另有三个任务恢复测试复跑通过。修复后没有重跑整套门禁，以上是完整首轮与精确失败复验的结果；完整门禁目前仍不能称全绿。

提交前检查：编码与 Ruff 通过，ESLint 0 错误、1,361 项既有警告，`npm run type-check` 通过。前端全量 1,330 通过、4 失败：三个日期/时区断言已在独立基线逐项复现；路由超时单独复跑四项全部通过。本轮未改前端代码，未修改这些断言。

## 验收边界

本次证明有限补齐、异常分类、预算与持久化行为符合 POC。客户原失败配对尚未在新代码上调用真实模型复验，不能据此声称实际恢复率或语义准确率已提高。客户历史 03-01-04 的瞬时失败后来诊断已成功，原始故障没有足够证据追溯；新日志用于定位今后发生的失败。

客户机仍运行旧交付包；需要后续部署新版本才会获得本次行为。
