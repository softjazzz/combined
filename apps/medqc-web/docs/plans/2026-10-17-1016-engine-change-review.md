# 1016 质控引擎修改说明（P0 失败隔离 + 第三轮业务回退修复），供独立核查

- 工作树：`D:\MedQC-worktrees\claude-next-20261016`，分支 `codex/claude-next-20261016`，基于 HEAD `396ef67d4`。
- 状态：全部为**未提交**改动（`git diff` + 3 个新文件），尚未推送。
- 范围：`apps/medqc-web/backend` 下 LX0609 引擎、结果收口、保存与补跑筛选。前端、数据库结构、规则目录 JSON 未改。
- 来源：
  - **A 部分（P0）**：主 agent 改，用户已批准“修正后的 P0”。
  - **B 部分（B1–B5）**：Codex 派活单 11 改，主 agent 审查后合入。
  - **C 部分**：主 agent 合入时的调整和补充。
- 不要暂存：`src/styles/index.prebuilt.css`、`backend/data/luxian_0609_opinion_freeze/`、`.claude/`。

## 0. 背景：为什么改

第三轮 27 例全量质控（任务 21fdde57）暴露两类问题。

**一、一个点出错，连带整族、整个病例乃至整批任务失败**

- 04-02-01 有 4 项“不合规但缺客户解释”，保存时校验失败，整批 27 例一起失败。
- 已排队的 42 项自动补跑一次都没执行，任务详情接口返回 409。

**二、技术失败被当成“资料不足”交付**

- 模型失败时交付了“资料不足”，等于让医院为模型失败补病历（G01 对应 01-01-02，G08 对应 07-01-03）。
- 来源截断被说成“数据源未接入”（G05）。

另有已核实的业务回退：

- G02：01-01-02 把只写在现病史里的症状算成了主诉线索；
- G06/G07：检验来源为空却判“九项全缺、不合规”；
- G11：07-01-01 套用九项合同，与业务基线不符。

设计原则：

- 不推倒重来，族分组、决策绑定、隐私校验、保存层最终检查都保留。
- 只把出错的影响范围收窄到单个点，并让技术失败带准确的原因码。
- 不增加统一重试，不做整族重跑。

## A. P0：失败隔离（主 agent）

### A1 客户解释合同抽成共用函数

- 新文件 `luxian_0609/customer_explanation_contract.py`：`customer_explanation_satisfied` 是唯一判定。规则是：LX0609 的 `non_compliant` 必须带已校验的展示事实，或者带已失败的受控子判定（只看前 8 条）。
- 这个模块不依赖 Finalizer，也不依赖保存层。原因是 `canonical_result_store` 已经依赖 Finalizer，反过来导入会形成循环。
- `qc_workspace/canonical_result_store.py` 的 `safe_criterion_results`、`validated_customer_explanation` 改为调用这个共用合同。保存时的校验保留，作为最后一道把关。

### A2 收口层单条检查、汇总层逐条兜底

- `canonical_result_finalizer.py`：
  - `finalize_luxian_0609_missing_decision_result` 支持传入 `reason_code`；
  - 新增 `CUSTOMER_RESULT_CONTRACT_VIOLATION`、`luxian_0609_customer_result_contract_holds`、`enforce_luxian_0609_customer_result_contract`；
  - 不满足合同的一条改判为 `technical_error/customer_result_contract_violation`；
  - `technical_error` 和 `uncertain` 不做这项检查。
- `luxian_0609_result_aggregator.py`：单条收口抛出 `TypeError`/`ValueError`/`KeyError` 时，只把这一条改判技术错误，并写一条告警日志（只记 rule_id 和异常类别）。
- **只在正式主链 `CANONICAL_RESULT_DELIVERY_MODE` 生效**。旧兼容交付模式仍然直接报错，因为有 93 条旧测试锁定这一行为。
- 病例身份、快照归属、整批结构错误仍在循环之前校验，照样阻断整批。

### A3 族输出逐点校验

`luxian_0609/execution_contract.py::validate_family_execution_envelope`：

| 情形                                | 改前                   | 改后                                                                                     |
| ----------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------- |
| 某点缺失                            | 整族所有点改判技术错误 | 只有这一点判 `family_result_missing`（同时有无法归属的条目时判 `family_result_invalid`） |
| 某点重复                            | 整族技术错误           | 只有这一点判 `family_result_duplicate`                                                   |
| 多余的点、无法归属的条目            | 整族技术错误           | 丢弃，其余照常                                                                           |
| 顺序不对                            | 整族技术错误           | 按调度范围重排                                                                           |
| `planned_rule_ids` 与调度范围不一致 | 整族技术错误           | **仍然整族失败**                                                                         |
| 所有点都需要改判                    | 整族技术错误           | **仍然整族失败**，保持原来的失败统计和用量口径                                           |

- 被丢弃或改判的点，它们的展示事实也一起剔除。
- 新增 `FamilyExecutionValidation.repaired_rule_ids`。
- `engine.py`：修复成功时写一条告警日志，内容只有 executor_key、原因码和修复条数，不含病历内容。

### A4 异常分类与隐私拦截日志

- `llm_prompt_privacy.py` 新增 `classify_luxian_0609_llm_call_failure`，按异常类型归类：

  | 异常                                                                 | 原因码                    |
  | -------------------------------------------------------------------- | ------------------------- |
  | 隐私异常（`PatientPrivacyViolation`、`PrivacyIdentityContextError`） | `privacy_guard_blocked`   |
  | 超时                                                                 | `model_timeout`           |
  | 程序缺陷类异常                                                       | `execution_program_error` |
  | 其余                                                                 | `model_transport_error`   |

- 隐私拦截时写一条安全日志，只含异常类别、executor_key、record_key_hash，不写提示词，也不写身份值。
- 改用分类函数的调用点：`transfusion_order_trigger.py`、`transfusion_course_presence.py`、`extended_document/discharge_approval_extraction.py`、`course_quality/rule_077.py`。
- `decision_model.py`：`technical_error` 允许的原因码新增 `customer_result_contract_violation`、`privacy_guard_blocked`、`execution_program_error`。

### A5 补跑筛选

`qc_workspace/failed_rule_retry.py` 新增 `_DETERMINISTIC_FAILURE_REASON_CODES`，命中的失败不自动补跑：

- 隐私拦截、程序异常、交付合同；
- `family_result_*` 结构类。

超时、传输、格式错误仍按原有策略补跑。

### A6 测试

- 新增 `tests/unit/test_luxian_0609_failure_isolation_p0.py`，14 项，覆盖：
  - 注入一个坏点，其余结果照常通过保存校验；
  - 坏点显示为技术错误；
  - 自动补跑只选允许重跑的失败点。
- 改写的旧断言：
  - `test_luxian_0609_execution_contract.py` 里两组“整族作废”断言，按新口径改写；
  - `test_luxian_0609_mainline_services.py::test_unified_engine_uses_registry_order_once_and_keeps_customer_order`：范围外的多余决策被丢弃，范围内保持 compliant。

## B. 第三轮业务回退修复（Codex 派活单 11，主 agent 已审）

| 项            | 质控点                    | 改法                                                                                                                                                                                                                                                                                                                                                             |
| ------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1（G01）     | 01-01-02 主诉导出第一诊断 | 三种模型失败（无客户端、调用异常、输出不合原子合同）：主诉字数超限时维持 `non_compliant`，否则判 `technical_error`（`model_transport_error` / `model_invalid_output`），不再判 `data_gap/source_readiness_unproven`。`native_course_quality_execution.py` 两条执行路径都改了。                                                                                   |
| B2（G02）     | 01-01-02                  | 用户已确认口径：只按主诉原文判断。上下文首行加 `[主诉原文]`；入院记录段标注“仅供核实病灶侧别、识别规范例外、理解术语”。提示词写明口径并给出反例。输出新增必填字段 `chief_complaint_signals`（1–6 项，每项不超过 20 字），每一项去掉空白和标点后必须是主诉原文的子串，否则视为输出不合合同。该字段不进入客户展示事实。判定口径 JSON 中 01-01-02 第 2 步同步更新。 |
| B3（G08）     | 07-01-03 输血前九项       | 输血病程分类返回 `technical_error` 时判技术错误，保留原因码；分类返回 `data_gap`（模型给出 unknown）时仍判资料不足。实施抽取的处理见 C1。                                                                                                                                                                                                                        |
| B4（G06/G07） | 07-01-01 / 07-01-03       | 已确认输血、检验来源为空或可读行为 0 时，内部原因记为 `pretransfusion_lab_results_absent`，对客户映射为 `source_unavailable`，文案是“输血前检验结果未取得或不可读”。有检验记录但缺项时仍判 `non_compliant`。                                                                                                                                                     |
| B5（G11）     | 07-01-01 输血前常规检查   | 按业务基线 043 改查 ABO、Rh、不规则抗体筛查加八项感染筛查，**不含 ALT**。`evaluate_pretransfusion_nine_items` 增加 `required_items` 参数；07-01-03 继续查九项，行为不变。同步更新：展示事实允许的项目键、Renderer 的项目标签和文案。`rh` 别名不按裸子串匹配。                                                                                                    |

- 新增 `tests/unit/test_luxian_0609_1016_run3_fx.py`。
- 改了 18 组旧断言，依据逐条列在 `D:\MedQC-worktrees\codex-runs-20261016\11-run3-fx\last.txt` 的 `changedOldAssertions`。

## C. 合入时主 agent 的调整与补充

### C1 实施抽取失败的影响范围（修正 B3 的判断顺序）

- **Codex 原写法的问题**：只要实施抽取失败，07-01-03 就整条改判技术错误。这样会丢掉结构化输血记录（mr_bloodtrans）本来就能成立的“不合规”结论。
- **现在的写法**（`native_extended_document_execution.py` 07-01-03 分支）：
  - 抽取失败，且没有结构化输血记录 → `technical_error`；
  - 有结构化记录 → 照常核对九项：
    - 结论为 `non_compliant` 的保留，因为它只依赖已确认的事件；
    - 结论为 `compliant` 且存在未确认的记录 → 改判 `technical_error`。改前这种情况降为 `data_gap`。
- **抽取器原因码**：`extended_document/transfusion_performance_extraction.py` 不再把三种模型失败合并成 `semantic_extraction_unresolved`：
  - 无客户端 → `model_transport_error`；
  - 调用异常 → 走 `classify_luxian_0609_llm_call_failure`；
  - 解析失败 → `model_invalid_output`。
  - 新增 `TECHNICAL_FAILURE_REASONS` 和 `PerformanceExtraction.technical_failure`。

### C2 07-01-01 的同类问题（派活单未覆盖）

`native_transfusion_execution.py`：07-01-01 在没有结构化输注事件时调用同一个实施抽取器。改前，模型失败会使所有记录变成 unknown，再交付为 `data_gap/transfusion_time_unavailable`。现在 `technical_failure` 为真时直接判技术错误，并保留细分原因码。

### C3 输血族技术原因码白名单

`native_transfusion_execution.py::_typed_decision_from_outcome` 的白名单加入 `model_timeout`、`privacy_guard_blocked`、`execution_program_error`。不加的话，这三类会被改写成可补跑的 `executor_exception`。

### C4 G05：来源截断单独给原因码

`native_transfusion_execution.py`：

- 类型化投影的触发来源检查：`unavailable` 仍对应 `transfusion_source_unavailable`；`truncated` 改为对应 `transfusion_source_truncated`。
- `_performed_source_state`：读取材料抛出 `EvidenceMaterialTruncated` 时记为截断。最终资料不足时，返回 `("data_gap", "transfusion_source_truncated")`。第二个返回值原来只用于技术错误，现在也承载截断原因，docstring 已同步更新。
- 交付资料不足时，用 `performed_error or "transfusion_source_unavailable"`。医嘱触发分支里 `performed_error` 先初始化为 `""`。
- 决策映射：`transfusion_source_truncated` → `ApplicabilityState.UNKNOWN` + `source_truncated`。客户文案沿用已有的“相关资料数量超过本次读取范围，当前资料不完整……”。

`canonical_result_finalizer.py`：07-01-02、07-02-01、07-02-02 的无事实资料不足放行清单加入 `transfusion_source_truncated`。

预期影响：C04、C08、C09 等医嘱被截断的病例，客户看到的原因从“数据源未接入”变为“资料不完整”。

### C5 检验项目别名

已在本地 `cdm.labtest_item_report` 只读核对项目名（只看项目名，不涉及患者信息）：

- **去掉梅毒别名 `tp`**：这是原来就有的错误。“\*总蛋白测定”的缩写也是 TP，库里 66 行，会被当成梅毒检查，07-01-03 九项一直受影响。本地真实的梅毒项目名称里都含“梅毒”。
- **去掉裸的“抗体筛查”**：它会同时命中“HIV抗体筛查”这类名字，一行命中两个项目时会被丢弃，HIV 反而被判缺项。保留“不规则抗体筛查”“意外抗体筛查”，新增“红细胞抗体筛查”。本地实际只有“不规则抗体筛查”。
- 本地的“*ABO血型鉴定”“*Rh血型鉴定”都能命中。

### C6 其他

- `transfusion_result_mapping.py`：07-01-01 的展示事实允许集合 = 九项 ∪ {abo, rh, antibody_screen}，**仍接受 alt**，免得前三轮已存的结果读出时被判为非法事实。
- `course_quality/rule_018.py`：提示词开头保留原来的定位句“你只从本次入院记录的主诉原文与受控第一诊断中抽取医学关系原子事实”，后面接新口径。
- `customer_remediation.py`：07-01-01 的标题“输血前九项检查”改为“输血前常规检查”。
- `customer_renderer.py`：05-01-04 的三句资料不足文案原来误放进 `_RULE_MISSING_ITEM_LABELS`（重复键，F601，e855b18a6 引入），覆盖了短标签。现在挪回 `_RULE_DATA_GAP_MESSAGES`。

### C7 C 部分的测试

- `test_luxian_0609_1016_run3_fx.py` 追加：
  - 抽取器细分原因码（4 种）；
  - 07-01-03 有结构化记录且抽取失败时，齐全判技术错误、缺 HIV 判不合规；
  - 07-01-01 抽取失败时保留 4 种原因码；
  - 医嘱截断时得到 `transfusion_source_truncated`；
  - 别名不交叉命中（HIV 抗体筛查、总蛋白 TP、梅毒 TPAb）。
- `transfusion_order_test_support.py`：替身新增 `performance_state` 参数，按 choices 结构应答实施抽取协议。原来替身应答不了这个协议，`test_short_actual_record_passes_gate_without_length_threshold` 是靠“模型失败被当成资料不足”才通过的。现在给它真实标注，测的仍是“缺开始时刻判资料不足”。
- 改动的旧断言：
  - `test_tc02_model_exception_is_one_call_technical_error_not_doctor_omission`：超时原因码 `model_invalid_output` → `model_timeout`；
  - `test_tc02_formal_privacy_wrapper_known_residue_still_fails_closed`：`model_invalid_output` → `privacy_guard_blocked`；
  - `test_tc02_frozen_marker_text_remains_body_and_cross_document_atom_rejected[True]`：`semantic_extraction_unresolved` → `model_invalid_output`；
  - `test_transfusion_truncated_shared_trigger_source_is_data_gap`：`transfusion_source_unavailable` → `transfusion_source_truncated`。

### C8 独立核查（Codex）发现后补修

Codex 核查结论：P0 方案成立，独立复验 815 项通过，11 个要点中 9 项成立、2 项发现缺口。主 agent 核实后补修了以下三处，都在新文件 `tests/unit/test_luxian_0609_1016_review_fx.py` 中有覆盖：

- `failed_rule_retry.py`：确定性失败集合补上 `family_result_order_mismatch`。新校验器已经直接重排顺序，所以这项主要影响历史失败数据。
- `native_transfusion_execution.py::_lab_item_key`：补读 `lab_item_name`，来源合同同时认可这个字段。这是改前就有的缺陷：只有 `lab_item_name` 的数据源，会被误判为“全部缺项、不合规”。
- `anesthesia_visit_fact_extraction.py`：模型失败（无客户端、调用异常、解析失败）原来返回 `data_gap/semantic_extraction_unresolved`，改为 `technical_error`，并给出细分原因码。这同样是改前就有的问题，影响 04-04-02。配套改动：
  - `native_surgery_document_execution.py` 遇到 `technical_error` 交付技术错误；
  - 手术文书族的技术原因码改为按白名单 `_PASSTHROUGH_TECHNICAL_REASONS` 原样保留，原来除 `source_query_error` 外一律改写成 `snapshot_mismatch`；
  - 模型给出 unknown 时，仍判资料不足 `semantic_extraction_unresolved`。

## D. 验证现状

- 相关 9 个测试文件共 1663 项：只有 1 个失败，`test_each_defined_rule_data_gap_names_customer_visible_missing_material[LX0609-03-01-05]`，在既有基线里。
- P0 单独跑的全量回归：18 个失败，与基线逐条一致。
- 合并及核查补修后的 LX0609 全量回归（含三个新测试文件）：10325 过、18 失败、1 跳过；18 个失败与基线逐条一致，新增失败为 0。
- ruff：改动文件没有新增问题。`test_luxian_0609_result_aggregator.py` 的 12 项 E701/F821 不在本次改动的行内，是原来就有的。
- `git diff --check` 通过。

## E. 请核查的要点

1. **影响范围是否真正收窄**：注入一个坏点，同族、同病例的其他点是否保留原结论，整批任务是否还能保存并触发补跑。是否还有遗漏的路径，会让单点问题扩散到整族、病例或任务。
2. **整体结构错误是否仍然阻断**：病例身份、快照归属、`planned_rule_ids` 不一致、整族全部缺失这几种情况，是否仍按整族或整批失败处理，没有被逐点修复“修好”。
3. **合同不放宽**：
   - 共用合同和原保存层校验是否等价（包括前 8 条子判定的范围）；
   - 隐私校验、决策绑定、保存层最终断言是否都没有放宽；
   - 隐私日志里是否不含提示词或身份值。
4. **原因码一致性**：
   - 新增原因码在 `decision_model` 白名单、输血族白名单、Finalizer 放行清单、Renderer 文案和补跑筛选里是否都已登记；
   - 有没有哪条路径仍会把它们改写成 `executor_exception`，或者落成 `data_gap`。
5. **补跑筛选**：确定性失败是否都被排除；可重跑的失败（超时、传输、格式错误）是否没被误排除。
6. **技术失败不交付为资料不足**：全仓搜索 `semantic_extraction_unresolved`、`source_readiness_unproven` 等资料不足原因码，看还有没有来自模型调用失败（无客户端、异常、解析失败）的路径。已知的有 `anesthesia_visit_fact_extraction.py`（第 169、183、188 行），不在本次范围，请判断是否属于同类问题。
7. **C1 的语义**：有结构化记录且抽取失败时，`compliant` 改判技术错误、`non_compliant` 保留结论，这样处理是否合理。`data_gap` 分支（时间缺失、登记缺失）是否不受影响。
8. **B2**：
   - 原文锚定在主诉含标点、空格、全角字符时会不会误判；
   - `unknown` 允许空数组是否会被模型钻空子，比如模型给出 supports 却把 kind 填成 unknown；
   - `_lx018_complaint_text` 在两条执行路径（`typed_documents` / `documents`）取到的是否是同一份主诉。
9. **B4/B5**：
   - `state == "empty" or not rows` 放在输血时间检查之后，顺序是否合理；
   - 07-01-03 的 `require_current_stay=True` 过滤之后，检验行全部被过滤掉时会走哪个分支；
   - 别名改动（去掉 `tp` 和裸“抗体筛查”）会不会造成漏命中。
10. **旧兼容模式**：A2 只在正式主链生效。确认生产默认确实走正式主链；旧兼容入口是否还有生产调用方。
11. **旧断言改动**：A6、B、C7 列出的旧断言改动，逐条判断依据是否成立，有没有用改断言掩盖真实回退。

## F. 核查方式与约束

- **只读核查**：不改已跟踪文件，不提交、不推送，不执行 reset、checkout、clean、stash。
- **不调用真实模型，不连接业务数据库**：本说明中的项目名核对已由主 agent 完成。
- 不读私有病历原文，`.tmp/*-private` 不在核查范围。
- 看改动：`git -C D:/MedQC-worktrees/claude-next-20261016 diff -- apps/medqc-web/backend`，另加 3 个新文件：
  - `app/services/luxian_0609/customer_explanation_contract.py`
  - `tests/unit/test_luxian_0609_failure_isolation_p0.py`
  - `tests/unit/test_luxian_0609_1016_run3_fx.py`
- 跑测试（在 `apps/medqc-web` 下；`<W>` 为该目录的绝对路径，DATABASE_URL 用自己临时目录里的 SQLite 文件）：

  ```bash
  PYTHONUTF8=1 PYTHONPATH="<W>/backend;<W>" DATABASE_URL="sqlite:///<临时目录>/x.db" JWT_SECRET=local-test-only-secret-0123456789abcdef PYTHONHASHSEED=0 python -m pytest <测试文件...> -q -o addopts="" -p no:cacheprovider --timeout=300 -W ignore
  ```

  LX0609 全集清单在 `apps/medqc-web/.tmp/1016-qc-review-private/lx0609-test-files.txt`，既有 18 个失败的基线在同一目录的 `baseline-18-failures.txt`。

- 回报：逐条给出“成立 / 有问题 / 存疑”和依据（文件:行）。发现的问题请附最小复现（合成数据）和建议改法。
