# DeepSeek 架构审计独立复核

复核日期：2026-09-13。代码基点：`de9cda3cf`，核查对象为本机工作区和本机历史质控库。未修改生产代码、数据库或共享台账，未调用真实模型。本文不代表客户机安装版本的验收结论。

## 结论与证据边界

审计抓到了需要修复的问题：禁止状态仍被正式结果合同接受；时区偏移可使确定性规则误判；同一模型响应中的单条非法事实会影响其他规则；调用次数合同没有运行时消费者。不能把审计中的全部结构统计都直接列为已复现 bug。

主协调 Agent 亲自运行了正式函数的合成输入探针、只读数据库汇总，并核对关键调用链。子代理仅做独立只读排查；未经主协调验证的推断不作为本文的确定结论。探针全部保存在已忽略的 `.tmp/0910-full-audit/`，不包含真实模型调用。

## 已确认的问题

### 1. 禁止状态的交付门禁缺失

当前加载的合同是 **77 条**，不是审计所写的 75 条；它们的 `allowed_final_states` 相同。搜索生产 Python 源码，这个字段只有声明、加载与自洽校验，没有按规则核验实际结果的执行消费者。

这里的缺失专指“将该字段用于最终业务结果的按规则成员检查”。合同构造校验、部分规则的局部校验、文书引用绑定和状态一致性校验确实存在，不能把整个合同体系称为空壳。

主协调直接调用 `canonical_envelope_items_are_consistent`：当 `status` 与 `result_status` 都是 `uncertain` 或 `technical_error`，且 `is_compliant=None` 时，函数返回 `True`。当前 `CANONICAL_RESULT_STATUSES` 明确包含这两态；客户结果读取路径通过这一校验后继续投影结果。因此它是有字段一致性校验、但没有落实当前业务禁交付要求。

主协调使用 `SET TRANSACTION READ ONLY`，按 `envelope_json.items[*].status` 精确统计，而非全文搜索：

| 本机历史数据统计对象 | 数量 |
| --- | ---: |
| 结果信封 | 793 |
| 信封内规则结果项 | 38,752 |
| 至少含一项上述禁止状态的信封 | 337 |
| `uncertain` 规则结果 | 524 |
| `technical_error` 规则结果 | 710 |

**337 的单位是信封，不是规则项，也不是当前版本误判病例数。** 这是历史持久化事实；不能直接推导“客户实际看过 337 份错误结果”。本轮没有在客户机执行查询或验证其安装版本。

定位：`backend/app/services/luxian_0609/rule_contracts.py:152`；`backend/app/services/luxian_0609_result_schema.py:18`；`backend/app/services/qc_workspace/canonical_result_store.py:109`；`backend/app/services/custom_qc_workspace_service.py:3110`。

验证产物：`deepseek-review-root-private.py/.json` 的 `contract_gate`；`deepseek-review-root-db-private.py/.json`。

### 2. 丢弃时区偏移会使 061 的结论翻转

`extended_document/shared.py` 解析带时区的时间后直接 `replace(tzinfo=None)`，没有先换算到业务时区。主协调调用正式 `evaluate_discharge_documentation_timeliness`，固定出院时间为北京时间 1 月 1 日 10:00，只改变同一个完成时刻的表示：

| 出院记录完成时间 | 正确间隔 | 当前函数间隔 | 当前结论 |
| --- | ---: | ---: | --- |
| 1 月 2 日 16:00，`+08:00` | 30 小时 | 30 小时 | 不合规 |
| 1 月 2 日 08:00，`+00:00`，与上行同一时刻 | 30 小时 | 22 小时 | 合规 |

这是**已复现的确定性误判**，无需模型参与。输入都是 `+08:00` 或统一无偏移本地时间时，不一定出现这个故障；不能据此断言历史样本已全部算错八小时。

定位：`backend/app/services/luxian_0609/extended_document/shared.py:15`；`backend/app/services/luxian_0609/extended_document/discharge_documentation.py:29`。

验证产物：`deepseek-review-root-private.py/.json` 的 `discharge_offset`。

子代理还在正式 050 执行器复现了同一机制：同一入院瞬时用 UTC 表示时错误提前达到七天阈值，判缺陷；用 `+08:00` 表示则尚未触发。主协调已审查合成 reader 和正式调用、重跑探针，并核对 `native_extended_document_execution.py:2076` 的资料与判定分支。该结论未依赖绕过 Bundle 的另一条数据库查询链。产物为 `deepseek-review-time-private.py/.json` 的 `rule_050_replay`。

### 3. 单条坏事实会影响同批其他待判规则

主协调使用合成的正式 EvidenceSnapshot / MaterialStore，运行 `execute_luxian_0609_native_exam_lab_rules`，只替换模型客户端为固定响应，随后经过正式绑定归约：

| 情景 | 011 | 012 | 015 | 模拟 `generate()` 次数 |
| --- | --- | --- | --- | ---: |
| 两条模型事实合法 | 合规 | 合规 | 不适用 | 1 |
| 仅 011 的 `semantic_state` 非法，重试仍返回同一坏值 | 技术错误 | 技术错误 | 不适用 | 2 |

因此异常传播成立，但范围是**共享响应中的待判规则**，不是所有规则或整份病历。015 的确定性结果没有被覆盖。当前解析器对部分语义矛盾已经做局部降级，也不能概括为“任何坏字段都全族失败”。手术族源码中存在相似批处理分支，本轮没有把手术族所有触发组合逐一动态复现。

`native_basic_timeliness.py:1936` 是程序执行异常处理，不能把它直接列为“001–006 被坏模型响应污染”的证据。其异常传播需要单独证明真实触发输入。

定位：`backend/app/services/luxian_0609/native_exam_lab_execution.py:2011`；`backend/app/services/luxian_0609/native_surgery_gate_execution.py:2511`。

验证产物：`deepseek-review-root-private.py/.json` 的 `exam_control`、`exam_single_bad_fact`。

### 4. 模型调用次数合同缺少运行时执行

主协调核对生产 Python 源码，`max_llm_calls_per_rule` 仅用于合同声明、加载与自洽校验。上述检查族探针已经走了两次包含 011/012 的调用，而合同相应值为 1。还需区分每条规则的语义调用预算、共享族调用，以及客户端内部 HTTP 重试；不能直接用族调用总数作为每条规则的独占成本。

定位：`backend/app/services/luxian_0609/rule_contracts.py:150`、`:199`、`:336`。

### 5. 输入预算需区分字段上限与总预算

复核更正：本报告初稿只跟踪 `resolve → _prompt`，曾把字段长度也写成没有限制；继续沿 `_diagnosis_item` 反查后，撤回这一判断。`malignancy_fact.py:197` 已将名称裁剪至 240 字符、编码至 32 字符，上游 Evidence Session 也有来源行数上限。**“完全无界输入”不成立。** `_prompt` 自身没有总字符/token 预算，以及该总量是否适配模型限制，才是应核对的边界；本轮未证明真实病例因总量溢出而失败。

017 则有每份文书 1200 字符的裁剪、候选对上限、512 输出 token 上限和禁止内部长度重试；4096 输入 token 检查在拿到响应 usage 后执行。它有前置字符边界，却没有调用前的总 token 检查。016 在该文件的对应判定为程序路径，不能将 017 的调用问题概括成“016/017 全族模型输入没有限制”。

定位：`backend/app/services/luxian_0609/malignancy_fact.py:182`、`:289`；`backend/app/services/luxian_0609/course_quality/rules_016_017.py:642`、`:748`、`:792`。

### 6. 内部长度重试的费用统计存在分层差异

主协调核对 `qc_llm_client.py:213` 至 `:280`：同一次 `generate` 可在 length 条件下发起第二次 HTTP 尝试。客户端总 token 与 `_usage_breakdown` 汇总两次尝试，返回的 `usage` 保留最后一次结果。会诊 `_usage` 与检查族 `_usage` 只读取后者，再由 `execution.py:897` 至 `:907` 汇总为 native 用量，因此这些统计路径会少计首轮 token。

这是具体消费者的计量缺陷，不是所有账本都系统性少报。逻辑调用一次、HTTP 尝试两次本身也需要先明确指标名称。恶性分类与 017 显式关闭长度重试，不受该重试问题影响；本轮没有实测客户当前模型恰好触发了这个条件。子代理报告过 mock 数字，但未提供对应持久探针，本文不引用其数值，只采用已亲验的代码路径。

429/5xx 也不能笼统称为“系统完全分不清”：`llm_observability.py:536` 分别记录它们，外层规则结果常统一为 `model_transport_error`。这是错误提示颗粒度的缺失，未证明它直接造成临床结论误判。

## 需要更正或降级的论断

| 原论断 | 独立复核后的结论 |
| --- | --- |
| 旧会诊模块可“零风险删除” | 无生产质控入口调用已确认；函数 2395 行的顶层 return 后，2404–2653 共 250 行不可达也已用 AST 确认。但 `backend/scripts/review_luxian_0609_semantic20.py:16` 仍导入其 `_context`，另有单测依赖。删除前必须处理这些依赖。 |
| 会诊生产解析器全用 `.get()`，等于没有校验 | 不成立。它校验枚举、条数、引用归属、建议结构及部分原文约束。探针中多余顶层字段会被忽略，非法 scope 会被拒绝。当前提示词本身没有规定 `schema_version`，不能拿旧协议的字段要求直接给新协议定罪。 |
| 旧严格校验器“导入了从未调用” | 字面上不成立。旧执行器 2256、2272 行调用了语义与规则事实校验器；准确描述应是这些调用未接入当前生产会诊入口。 |
| 017 证据读取异常被吞后，会交付无证据的不合规结果 | 在正式 typed 绑定链上已证伪。主协调注入材料定位异常，规则中间产物确实为 defect 且 refs 为空，但 `decision_binding.py` 将它转成 `technical_error / snapshot_mismatch`。异常诊断信息损失仍是问题，不能说完全没有拦截。 |
| 中间结果 `technical_error.is_compliant=False` 会被正式主链当成不合格 | 未证明。主协调核对 finalizer 1086 行后会将该兼容字段改为 `None`，正式写入/读取还校验字段一致。旧导出旁路会按 false 收入问题清单，但当前 LX 导出入口另走客户安全导出，不能用旧分支代码证明客户已收到误判。 |
| 正式目录旧状态词表与引擎“完全不相交” | 不成立；至少共同包含 `not_applicable`，`luxian_0609_result_schema.py` 还定义了 hit 等旧态映射。真正缺陷是缺少按单规则许可集合执行的门禁。 |
| 编排双路径同时开启，所以静默丢结果 | 不能成立为现有证据结论。旧执行分支有 `not unified_engine_used` 条件；绑定层会检查 missing/duplicate/unexpected 并逐项补技术错误；`canonical_result_store.py:544` 还按本次请求规则集合校验后再写入。读取接口也返回缺失项与 `is_complete`。不能把“没有一处总数相等 assert”说成“全链没有完整性保护”。 |
| 只有 012 能冻结或回放 | 混淆了生产缓存、诊断捕获、离线固定响应回放。会诊第一阶段确有生产事实缓存；会诊与 027 等已有离线 ReplayClient。后续语义阶段没有缓存，并不自动等于程序 bug；缓存也不能证明事实正确。 |
| 不同输入裁剪实现必须全部合并 | 多份实现是维护成本信号。必须先证明被截掉的必要证据造成了何种错误；否则不能以此直接启动公共重构。 |
| 入院锚点四套优先级说明四条活链都错 | 尚不成立。基础锚点与 050 均先注册表后入院记录，旧 evidence 生成路径也不能自动计作当前规则入口。同一注册行两个时间字段冲突时，基础锚点返回冲突，050 取首字段继续判定，这个差异已经用合成资料证明，真实病例影响尚未量化。 |
| 93 个宽异常分支未直接返回合规，说明这条方向安全 | 该统计只排除了“异常块直接写合规常量”。它没有排除异常后空数据在下游变为不适用、证据丢失或错误原因被掩盖。本文没有重新核验 93 处这个数量。 |

017 的验证产物为 `deepseek-review-root-private.py/.json` 的 `copy_evidence_binding`；旧模块与会诊解析器分别见 `old_consultation_module`、`consultation_validation`。这些验证都是合成输入，不是新增临床口径。

## 建议的修复顺序

1. 先修会直接改变判断的时区换算问题，以 061 的同一时刻不同表示为最小闭环，再检查同一解析函数的调用者。不得将所有无时区日期强行当成 UTC，也不得丢掉日期精度。
2. 落实禁止状态与交付合同：技术失败保留在任务状态、诊断记录中，不能伪装成 `data_gap`、合规或不适用，也不应通过放宽 AGENTS 规定来“消除缺陷”。写入与读取的职责要共同核对，保留可重试与具体定位。
3. 对 011/012 共享响应做最小错误隔离试验：只保留身份、来源和字段已独立校验通过的其他事实；整段无效 JSON、重复或跨事件引用仍需拒绝。比较同一输入的状态、证据、调用数和耗时。
4. 统一定义逻辑调用与实际 HTTP 尝试的计数含义，再补相应预算执行及明确的无界输入上限。先覆盖确认的问题点，避免扩展成通用框架。
5. 最后处理旧模块清理、文件体积、开关数量等维护事项。它们不应挤占准确性问题的优先级。

所有重试计量消费者以及各族超限状态的完整影响面，仍须在对应修复的小闭环内核实。不能仅凭函数数量或默认优先级不同就认定所有规则错误。本轮完成的是问题复核，尚未实施上述修复。
