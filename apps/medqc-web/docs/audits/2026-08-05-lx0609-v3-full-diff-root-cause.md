# LX0609 v3 修复后全量差分清账（只读）

> 本报告只比较已保存任务结果，不修改规则、Bundle、Reader、Envelope、API 或前端。

## 1. 冻结运行基线

| 项目             | DG-1旧任务                                   | 当前修复后任务                           |
| ---------------- | -------------------------------------------- | ---------------------------------------- |
| Git commit       | 2bcd1e16e99ecbfa4629b1cc334334077bb3f704     | cf7da5067dd6d002cddad6850b5a6d658fbb28cc |
| 任务 ID          | 1f63f39e-6ce2-44f7-a86b-5d65032e93a9         | b2feba05-b9e9-4296-a29b-255e78594991     |
| 病例/规则        | 38 / 75                                      | 38 / 75                                  |
| 任务范围         | all（旧任务）                                | final（当前任务）                        |
| Scene快照        | {'final': 36, 'running': 2}；缺出院时间 2 份 | {'final': 38}；缺出院时间 0 份           |
| 执行配置         | fast_screen / throughput_v1 / minimal        | fast_screen / throughput_v1 / minimal    |
| Token / 执行耗时 | 105150 / 375.53s                             | 38100 / 259.74s                          |
| 固定后端         | —                                            | PID 2932，127.0.0.1:8001                 |

当前任务实际保存 `38 × 75 = 2,850` 条结果；服务端统计为：

| 最终状态       | DG-1旧任务 | 当前任务 | 变化 |
| -------------- | ---------- | -------- | ---- |
| compliant      | 353        | 224      | -129 |
| non_compliant  | 322        | 370      | 48   |
| data_gap       | 651        | 265      | -386 |
| uncertain      | 64         | 8        | -56  |
| not_applicable | 1460       | 1983     | 523  |

**可比性警告。** 两个任务不是完全同输入：DG-1 是 `all`，其中 36 份 final、2 份 running 且 2 份没有出院时间；当前按 v3 样本池重新冻结为 38 份 final，38 份均有 `2026-06-13 18:00:00` 出院快照。旧任务的资料包也明显更大。因而“旧非缺口 → 当前 data_gap”不能直接认定为代码回归。

## 2. 651 条 DG-1 data_gap 逐条结果

| 差分类别                          | 条数 | 判定口径                                                                                |
| --------------------------------- | ---- | --------------------------------------------------------------------------------------- |
| 当前已形成确定结论（输入已变化）  | 429  | 当前任务已有确定状态，且有结构化事实/门控结论或明确客户结论；不能证明旧任务是引擎假报错 |
| 仍应保留的真实缺失                | 138  | 当前仍为 data_gap，源/字段/事件时间缺失有证据                                           |
| 状态变化但证据不足                | 4    | 状态变化或仍缺口，但当前证据不足以证明首次丢失层                                        |
| 仍未定位                          | 80   | 适用性/关联资料不足，不能归因单一 Reader                                                |
| 新增 data_gap 候选（不在651条内） | 47   | 旧任务非 data_gap、当前变 data_gap；47条输入签名均改变，当前0条可确认是代码回归         |

DG-1 651 条到当前任务的主要状态转移：

| 旧状态 → 当前状态         | 条数 |
| ------------------------- | ---- |
| data_gap → non_compliant  | 54   |
| compliant → data_gap      | 27   |
| data_gap → data_gap       | 218  |
| data_gap → not_applicable | 350  |
| not_applicable → data_gap | 7    |
| non_compliant → data_gap  | 12   |
| data_gap → compliant      | 25   |
| data_gap → uncertain      | 4    |
| uncertain → data_gap      | 1    |

当前 data_gap 共 **265** 条：其中 **218** 条是 DG-1 残留，**47** 条是旧任务非 data_gap 在新输入快照下出现的“新增 data_gap 候选”。

## 3. 当前 data_gap 按规则

| 规则       | 当前 data_gap | 当前 reason_code                                       |
| ---------- | ------------- | ------------------------------------------------------ |
| LX0609-051 | 37            | applicability_source_gap:37                            |
| LX0609-060 | 37            | applicability_source_gap:37                            |
| LX0609-071 | 35            | source_unavailable:35                                  |
| LX0609-018 | 32            | required_field_missing:32                              |
| LX0609-007 | 24            | authoritative_time_missing:24                          |
| LX0609-010 | 15            | authoritative_time_missing:10,required_field_missing:5 |
| LX0609-011 | 15            | authoritative_time_missing:10,required_field_missing:5 |
| LX0609-012 | 15            | authoritative_time_missing:10,required_field_missing:5 |
| LX0609-003 | 10            | authoritative_time_missing:10                          |
| LX0609-028 | 10            | required_field_missing:10                              |
| LX0609-039 | 7             | applicability_source_gap:7                             |
| LX0609-024 | 5             | required_field_missing:5                               |
| LX0609-049 | 5             | source_unavailable:5                                   |
| LX0609-025 | 4             | required_field_missing:4                               |
| LX0609-016 | 3             | required_field_missing:3                               |
| LX0609-005 | 2             | required_field_missing:2                               |
| LX0609-006 | 2             | required_field_missing:2                               |
| LX0609-047 | 2             | required_field_missing:2                               |
| LX0609-062 | 2             | required_field_missing:2                               |
| LX0609-014 | 1             | required_field_missing:1                               |
| LX0609-015 | 1             | required_field_missing:1                               |
| LX0609-069 | 1             | association_failed:1                                   |

## 4. 重点规则核对

### 4.1 LX0609-033（原 20 条）

| 当前状态/原因                           | 条数 |
| --------------------------------------- | ---- |
| not_applicable / performed_event_absent | 9    |
| non_compliant / requirement_violated    | 11   |

逐病例结果：

| 病例                   | 当前状态       | 当前原因               | 客户可见结论                             |
| ---------------------- | -------------- | ---------------------- | ---------------------------------------- |
| LX0609_0426_SYN_V3_001 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_008 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_009 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_010 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_017 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_019 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_020 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_021 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_023 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_024 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_025 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_026 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_027 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_028 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_029 | non_compliant  | requirement_violated   | 已确认实施手术，未检索到手术知情同意书。 |
| LX0609_0426_SYN_V3_032 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_033 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_035 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_036 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |
| LX0609_0426_SYN_V3_038 | not_applicable | performed_event_absent | 本次未实施手术，不要求形成手术知情同意书 |

结论：20 条均已脱离 data_gap；9 条明确“未实施手术，不要求形成手术知情同意书”，11 条明确“已确认实施手术，未检索到手术知情同意书”，并携带 `surgery_consent_document_missing` 事实。该规则本轮未继续改代码。

### 4.2 LX0609-071（原 35 条）

| 当前状态/原因                 | 条数 |
| ----------------------------- | ---- |
| data_gap / source_unavailable | 35   |

35 条全部保留 `data_gap / source_unavailable`。统一客户文案为：**当前缺少经治医师变更时间、交班记录或接班记录时间，暂时无法完成核对**，并明确建议确认医师变更及交接班资料已同步。

当前输入资料摘要没有交接班/接班事件来源；因此该结果应保留数据不足，不能改成不合规。

### 4.3 `other_with_evidence` 原 118 条

| 当前状态       | 条数 |
| -------------- | ---- |
| not_applicable | 59   |
| data_gap       | 48   |
| non_compliant  | 11   |

其中残留 data_gap 48 条，构成为：{'LX0609-016': 3, 'LX0609-071': 35, 'LX0609-028': 1, 'LX0609-005': 2, 'LX0609-006': 2, 'LX0609-025': 1, 'LX0609-047': 2, 'LX0609-062': 2}。033 的 20 条已全部脱离 data_gap；071 的 35 条全部保留；其余 13 条为明确的文书/字段缺失（016、005、006、047、062、025、028）。在这 118 条中没有发现“当前新产生、但没有任何资料证据”的额外假 data_gap。

### 4.4 `authoritative_time_missing` 原 118 条

| 当前状态       | 条数 |
| -------------- | ---- |
| not_applicable | 40   |
| non_compliant  | 30   |
| data_gap       | 30   |
| compliant      | 18   |

当前仍为 data_gap 的 30 条具体是：LX0609-007 17 条（病情稳定期间查房时间缺失）、LX0609-003 8 条（手术结束/记录/单台关联时间缺失）、LX0609-039 5 条（术前讨论适用性与术者参加资料不足）。它们的当前原因不再是任务评价终点缺失。

判断：这 118 条中，88 条在当前输入下已形成确定状态，其中 86 条是 `final → final`，仅 2 条是 `running → final`。旧任务有 2 份 running 且无出院时间，当前任务已冻结 38 份 final 出院时间；但跨任务资料签名、Bundle 内容和字段映射也同时发生变化，因此不能把这 88 条全部归因于 Scene 或评价终点，也不能据此证明是合成病例缺失。剩余 30 条在当前输入下仍缺少相应事件时间、文书字段或适用性资料，具体首次丢失层仍需同一 Scene/Bundle/EvidenceSnapshot 的只读复核。

## 5. 新增 data_gap 候选

旧任务非 data_gap → 当前 data_gap 共 **47** 条，按规则：`{'LX0609-007': 7, 'LX0609-018': 32, 'LX0609-003': 2, 'LX0609-028': 1, 'LX0609-014': 1, 'LX0609-015': 1, 'LX0609-024': 1, 'LX0609-051': 1, 'LX0609-060': 1}`。47 条的旧/新资料输入签名（文书数、正文长度、source table counts）全部不同；同时任务范围从 `all` 变为 `final`。因此当前证据只能标记为**新增 data_gap 候选/状态变化但证据不足**，不能确认是代码回归。

| 规则       | 候选条数 | 主要当前原因               |
| ---------- | -------- | -------------------------- |
| LX0609-018 | 32       | required_field_missing     |
| LX0609-007 | 7        | authoritative_time_missing |
| LX0609-003 | 2        | authoritative_time_missing |
| LX0609-028 | 1        | required_field_missing     |
| LX0609-014 | 1        | required_field_missing     |
| LX0609-015 | 1        | required_field_missing     |
| LX0609-024 | 1        | required_field_missing     |
| LX0609-051 | 1        | applicability_source_gap   |
| LX0609-060 | 1        | applicability_source_gap   |

需要单独冻结同一 Scene、同一 Bundle 和同一 EvidenceSnapshot 后，才能把这些候选升级为“确认回归”。本轮不修规则。

## 6. 根因与是否进入修复

按“影响至少 3 条且首次丢失层明确”的门槛，当前只得到以下候选，但均不满足立即改代码的安全条件：

| 候选根因                                                   | 影响                                        | 首次可见异常层           | 本轮结论                                                    |
| ---------------------------------------------------------- | ------------------------------------------- | ------------------------ | ----------------------------------------------------------- |
| 交接班/医师变更资料源未接入（071）                         | 35                                          | source_registry          | 资料合同/源库能力缺口，不是已有规则读取逻辑可安全修复       |
| 跨任务资料输入差异（含 Scene/评价终点、Bundle 和字段映射） | 至少 88 条时间根因结果、47 条 data_gap 候选 | 任务输入/资料快照        | 当前任务已按 final 快照执行；需同一输入复跑才能证明代码问题 |
| v3事件资料缺失（003/007/039）                              | 30 条残留                                   | native_result_projection | 更像合成资料缺少事件时间/适用性字段，不能直接改引擎         |

因此本轮 **0 个确定性生产代码修复**。没有新增 LLM 调用、没有修改规则口径、没有新增证据链、没有修改 Canonical/Envelope/API/前端。

## 7. 交付物与限制

- 差分明细：`C:\tmp\medqc-lx0609-review\v3-full-diff-details.csv`（651 条 DG-1 data_gap + 47 条新增 data_gap 候选，共 698 行）
- 本报告：`D:\LLM\LX888\apps\medqc-web\docs\audits\2026-08-05-lx0609-v3-full-diff-root-cause.md`
- 结果来源：固定后端 8001 的任务 `b2feba05-b9e9-4296-a29b-255e78594991`；对照 DG-1 任务 `1f63f39e-6ce2-44f7-a86b-5d65032e93a9` 与 DG-1 CSV。
- 本轮只读，未提交规则或资料修改；下一步如需修复，必须先批准具体候选并用同一资料快照建立失败测试。
