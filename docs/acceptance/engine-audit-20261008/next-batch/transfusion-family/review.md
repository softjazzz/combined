# TC-01 / TR-044-MULTI 下一步限定准备

完成层级：固定源码和既有合成证据的独立静态准备。0 次探针/测试执行，0 生产/共享测试修改，未读取 `.env`、PG、真实私有材料或调用模型。未宣称 TC-01 或 TR-044-MULTI 关闭；本轮不拓展全输血目录。

根固定源码 `e5f5696f559b4571b0d2a7d339d0d65485f8344b`。只读对照 TC02 候选 `219b13d5881e106a4780e0d9ba1f12620d7e3900`，它在本次根基线尚未合入，范围仅 070。`manifest.json` 保存 12 份固定 blob/hash，`source-anchors.json` 保存函数位置。根 native_transfusion_execution.py 与原 TC-01 快照 `7b894dc84491b7b72eb096de58fe61f772cc0080` 字节相同；旧纯函数观察可说明现有机制，但没有新整链执行。

## 旧证据精确定位

原报告：`docs/acceptance/engine-audit-20261008/treatment-consultation.md/.json`，TC-01 对应 JSON `/findings/0`。独占原冻结来源 `.tmp/engine-audit-20261008/treatment-consultation/frozen-expectations.json`，原 SHA256 `40fa02375634a4393cadccb439e79c466d114fb2ea7e8156888dcfac1d3a8371`。本目录 `tc01-original-cases.json` 精确保留六个 TF_* 合成输入/原预期/旧观察及原脚本、结果 hash；原脚本副本仅归档，未执行。其它 0916 旧内容排除，不计本任务。

| ID | 原冻结预期 | 原观察与边界 |
| --- | --- | --- |
| TF_PLAN | data_gap | 仅拟明日输注仍 gate=present |
| TF_REFUSED | data_gap | 患者及家属拒绝仍 gate=present |
| TF_POSTPONED | data_gap | 血源不足暂缓仍 gate=present |
| TF_CANCELLED | data_gap | 明确取消、未实施，旧 gate=data_gap 正常控制 |
| TF_ACTUAL_NO_REACTION | present | 明确开始输注且无反应，旧 gate=present 正常控制 |
| TF_PLAN_COMPLETE_FIELDS | data_gap | 全文是计划仍 gate=present；046 纯函数进入 non_compliant/transfusion_purpose_or_indication_missing |

这些旧结果是原源码 AST 纯函数依赖闭包观察，没有完整 Typed、Finalizer、保存/API 执行。不得将六个 gate 场景称为五规则各六项正式验收。

TR-044-MULTI 的原三项反例 node、原 rows、独立冻结 expected manifest **unknown**。公开 `2026-10-08-isolated-qc-integration.md:32` 只证明“三项多事件候选在基线亦失败”；`2026-10-08-0609-outcome-reconciliation.md` 保留多事件开放。D 的 `independent-review.md` 明示三项不在其认证范围；registry 独立确认没有精确三项索引。本轮已只读核对公开命名的 native_transfusion_execution、native_transfusion_freeze、rule_044_policy 测试入口，没有找到能可靠绑定为原三项的节点。不猜测三条，不用新造案例冒充旧 freeze，也没有打开 private 输入。既有 `db4bddb67` 的 044 字段/状态/保存合同关闭保持，TR-044-MULTI 是上游逐次事实关联的独立残留。

## 共用 helper 和各规则还缺的事实

固定 native_transfusion_execution.py:2865 `_dedicated_record_supports_performance` 排除少数取消/未输血短语后直接返回 `len(content)>=16`。2874 `_performed_source_state` 同时用于 legacy 和 Typed，2927 的正式 executor 逐规则调用，043–047 都经过它。专用正文长度不能证明实施；“无输血反应”也不能反向解释为未实施。

| legacy / 规则 | 门控后消费位置 | 可复用部分 | 实施以外仍需的事实 |
| --- | --- | --- | --- |
| 043 / 07-01-01 | `evaluate_pretransfusion_nine_items`:1160 | 确认实施事件、同快照来源引用 | 每实际事件的可信时刻、九项结果和报告时间、逐事件检查；不能用文书完成时间单独证明实施 |
| 044 / 07-01-02 | `_programmatic_044_status`:1383；pretransfusion_assessment.py:151/276 | 实施事件和来源定位 | 每次事件与申请单的身份/时序关联、申请理由及客观指标，逐次覆盖和未决关联；单一性能状态不能代替它们 |
| 045 / 07-02-01 | `_programmatic_045_status`:1571 | 实际事件对应记录视图 | 实际输血病程是否存在及归属；当前 any(substantive) 只证明有一份，不能以其它事件文书覆盖全部事件 |
| 046 / 07-02-02 | `_programmatic_046_status`:1658、字段检查/成分候选 | 实施及同文书连续引用校验 | 每份实际记录的目的/指征、起止时间、成分、剂量、过程观察、反应处理；成分/数量属于该事件，不能借计划或其它记录拼齐 |
| 047 / 07-03-01 | `_programmatic_047_assessment`:1974 | 实际事件及已消费引用 | 每次结束时刻、对应评价正文和完成时间、冻结评价终点、24小时窗口成熟性与疗效评价；一次 performed 不证明评价完整 |

044 结构化路径当前在 pretransfusion_assessment.py:184 和 :287 取 `event_times[0]`；两个路径都仅以最早事件选择一张申请或一个理由 candidate。:121 `_source_document_refs` 按时间最近选择专用记录；非结构化 :1383 分支 any(complete) 可以全局命中一份评估。以上是固定源码的机制定位，不是新运行、不是已绑定原三项失败 node。TR-044-MULTI 后续须先取得原精确 manifest 再冻结逐次预期，不能用这一静态机制替代原反例证据。

## TC02 能复用什么，不能直接迁移什么

TC02 `extended_document/transfusion_performance_extraction.py` schema 是 `lx0609-transfusion-performance-v1`：每文书恰一次 `performed/plan/cancel/unknown`，同文书动作 atom 和可选 event_time atom。可复用严格字段/唯一ref/完整覆盖、连续原文引用、bool 坐标拒绝、脱敏及范围预算、同快照材料定位和不让模型输出质控结论的职责边界。

它只为 070 有限单事件设计，不能直接接到五规则并宣称同族完成：

1. **预算不同。** 根 contracts 中 043/047 是 `program_only/max0`；044/045/046 是 `program_then_optional_llm/max1`，已有申请理由、成分或通用 fallback 调用。额外性能调用会改变 0-call 合同或形成 2 calls。须由根明确共享抽取的计量归属、旧窄抽取预算及目录版本，不能隐式增加调用，也不能删原理由/成分验证追求一调用。
2. **多时钟能力不匹配。** TC02 :81 `_parsed` 将正文多个 HH:MM 当 unknown，唯一时间 atom 还须等 record_time。正常 045/046 常有开始和结束两时刻，文书完成时间又不同于开始；现有 `test_transfusion_freeze_complete_multiple_events_keeps_customer_contract`（freeze 文件:88）明确保留 14:20/16:10 与 record_time16:20、18:00/19:00 与 record_time19:10，并要求 045/046/047 合规、计数2和真实来源。直接套 v1 会把这些正常记录压成能力 gap，不能以普遍资料不足当修复完成。一文书多次事件亦不在 v1 闭环范围。
3. **只改 gate bool 仍不够。** 有 MR 或另一条实际正文使 gate=present 后，原 documents 仍将 plan/cancel/unknown 专用行送入 044.any、045.any、046.all、047.end_rows。必须区分实际事件供临床核对的记录和已消费但未确认的材料；否定资料不能否定另一个 MR 实施，计划不能证明缺项或拼齐字段。过滤后为空也不能冒充物理 source=empty；原来源完整性、不可用和关联未决必须保留。
4. **时间和事件不是文书计数。** TC02 保留的 `unconfirmed_record_count` 是文书数量，不是漏验事件数；不能原样作为五规则事件计数。070 既有 record_time 文书时间合同不自动授权 043/044 的真实实施起点或 047 的结束时间。start/end/评价时间需要明确角色和关联；不得按时间 set 去重假装不同事件已全部覆盖。

合法 unknown、源不可用、协议非法和已确认缺陷须区分。当前五规则有 `evaluation_unknown`、来源 data_gap、引用/协议 `technical_error` 等既有分支；不将所有 unknown/非法协议改为 data_gap。旧六个特定冻结输入的预期保持原值。混合材料中已证 non_compliant 不应因旁边未知事件被全局抹掉；也不能用一项 compliant 宣称全部实际事件完成。具体归约和公开事实须由原合同与事件 schema 冻结，当前报告不改医学预期。

## 最小接入差异及文件所有权准备

所有权是给根下一批分工的建议，**本轮未分配或修改生产**；机器索引见 `ownership.json`。

- TC-01 owner：native_transfusion_execution.py 中仅 043–047 的实施接入、实际记录视图和同快照消费引用。共用 helper 还服务 041/042/048/049，不能直接全局换行为扩到排除/暂停或重开 TC-03；保留原规则边界。
- TR-044-MULTI owner：pretransfusion_assessment.py 的结构化申请选择、理由 candidate 和事件—申请关联；native 的 044 接口与上一 owner 协调。先收回原三项 node/rows/expected，保留现有单事件、严格提前、缺时间、同业务 ID 双来源和合法合同保护。
- TC02 owner/根协调：新 extraction 模块尚属 070 候选。不复制为另一套不受控 helper，也不私改它扩大多事件能力。若需要新事件 schema，独立版本化并补实际 start/end、事件身份等必要事实；070 原单事件、时间/状态/引用/预算保护必须继续成立。
- 根协调维护目录 contract/prompt/call budgets。transfusion_result_mapping.py、Finalizer、Renderer/Store 公共边界仅在新增公开事件事实确实需要时接线；内部模型 assertions/原文 atom 不直接发布，不为隐藏差异改全局投影。旧合法 fields/kind 与 `db4bddb67` 关闭成果保留。
- 实施 owner 的独占新测试：先保留原 TC01 六冻结、正常无反应和现有 045/046/047 多时钟多记录合规 freeze；TR 原三反例须取回后原样绑定。随后才准备混合 actual+plan/cancel/unknown、正逆顺序、多个实际事件与逐次申请/字段/评价归属，以及预算/非法atom/来源绑定保护。当前没有创建或运行这些新测试。

后续关闭门禁包括固定修复 SHA 差分、独立原反例与正常保护、真实执行器→binding→Finalizer 的消费验证，以及有公开事实改变时的保存/新实例回读/API投影。合法模型替身工程绿不代表真实语义或客户部署链通过。当前070仍是有限单事件工程候选，不证明整族完成。
