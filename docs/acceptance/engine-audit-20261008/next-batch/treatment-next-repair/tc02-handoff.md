# TC02 下一轮最小交接包（只读静态准备）

固定集成 SHA：aa7a98c7e43bc23439db485fa56cd90ea6da4bd1。范围仅 LX0609-07-01-03（旧 070，extended_document）；0916 排除。该轮未执行测试、模型、PG、env 或生产修改。历史探针源 SHA 为 7b894dc84491b7b72eb096de58fe61f772cc0080。

**阻断：暂停 MR-only 或无条件删除 bloodtrans_record.record_time 的生产方案。** 当前既有正常合同允许 mr_bloodtrans 为空，专用记录 record_time + “悬浮红细胞2U输注完毕。”作为实际输血时间并判九项合规。取消反例和这个正常用例共享相同结构字段，差异在正文。结构时间字段本身无法区分实施、计划、取消；正常 C 不可改 gap 凑通过。

## 原反例与固定配对

原反例 070_CANCELLED_RECORD_TIME：登记 admission_datetime=2026-10-08 07:00:00；mr_bloodtrans 完整空；bloodtrans_record 单行 document_id=CANCEL1、record_time=2026-10-08 08:00:00、record_content=“患者原计划输血，经再次评估后取消，本次住院未实施输血。”；检验完整空。旧探针模拟 070 分支，把该行合入 mr_bloodtrans 后调用纯九项 evaluator。冻结期望 data_gap；旧观测 non_compliant/pretransfusion_items_incomplete，且 performed_transfusion_confirmed=true、checked_transfusion_times=[2026-10-08 08:00:00]。这是分支输入及纯函数回放，不能称完整执行器复测。

来源：
- F:/MedQC-worktrees/qc-integration-20261008/.tmp/engine-audit-20261008/treatment-consultation/extension-frozen-expectations.json（SHA256 3077945601ca54174a167f1070bff8bc8788f1eabbdee598d29cde9bbb776303）
- 同目录 extension-results.json。

交接 JSON 提供一组待 critical owner 离线冻结/红测的固定配对：沿用既有正常用例的登记、专用记录时间和九项报告，仅改正文。正常为“悬浮红细胞2U输注完毕。”，期望 compliant/requirement_satisfied；取消为原反例正文，期望 data_gap，不断言本住院未输血，不生成九项缺陷，不改成 NA。此配对本轮**未执行**，不能当成新的通过或失败证据。

## 正式合同及精确源码位置

以下路径均以 F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/ 为前缀。

| 文件与位置 | 可以确认的合同/行为 |
|---|---|
| backend/app/database/models/cdm.py:1274、1293 | MrBloodtrans 是病案首页输血记录明细；transfution_datetime 为 DateTime，“输血时间”。支持继承现有 CDM 实施事件合同；不声称院端字段字典或 ETL 已验证。 |
| backend/app/database/models/cdm.py:32、931 | DocumentMixin.document_status 是文档状态；BloodtransRecord 正文为非结构化全文。没有可信的输血执行状态映射，不得将文档状态臆作 performed/cancelled。record_time 未在该模型声明为输血实施时间。 |
| backend/app/services/luxian_0609/source_evidence_reader.py:137、145 | mr_bloodtrans 白名单含 transfution_datetime；bloodtrans_record 白名单只含 ID、标题、正文、record_time，无执行状态。 |
| backend/app/services/luxian_0609/source_registry.py:515、605 | 两类输血记录作为实际输血锚点；070 要求本次住院九项早于每一笔实际输血。来源类型约束不能证明每行正文都已实施。 |
| backend/app/services/luxian_0609/native_extended_document_execution.py:3131、3144 | 无条件合并两类来源为 actual_transfusion_rows，并把合并列表传成 mr_bloodtrans。既有补丁没有关闭 TC02。 |
| backend/app/services/luxian_0609/native_transfusion_execution.py:961 | 公共时间解析最后回退 record_time；不是专用文档实施状态证明。 |
| backend/tests/unit/test_luxian_0609_native_extended_document_execution.py:7423 | 既有实际专用记录正常：mr 完整空、record_time=2026-06-02 14:00:00、正文输注完毕、九项=同日10:00，期望 compliant；还要求 bloodtrans_record evidence ref。 |

仅删除时间回退，会破坏以上 7423 正常。现有正式来源没有可直接消费的可信实施状态，不能通过扩否定词、关键词或给文档状态新造词表解决。

## 下一步范围与正常保护

critical owner 的第一步仅冻结固定配对及原反例，然后在离线链路复现红例；禁止盲撤 record_time。生产修复需要受控实施事实或上游可信状态，携带 performed/planned/cancelled/unknown、来源证据、实施时间和事件归属。枚举名称不是已存在可信输血事实；本包没有建立新临床状态词表。

专用记录无可信实施时间/事实应 data_gap，不是 NA。原正常专用实际记录必须继续 compliant；若无法同时满足，报告合同输入不足并保持红例，不重写正常期望。

需要保留的已存在正常边界（仅静态读取，未重跑）：
- 实际 mr 行 + 输血时间 + 更早本住院九项：7392。
- 无权威输血时间：7517，data_gap/authoritative_time_missing；仅 record_time 的未知正文同样不能确认实际输血。
- 仅实际专用记录 record_time：7423，不可回退。
- 专用来源不可用：7469，data_gap/source_unavailable，不可 NA。
- 多实际 mr 事件：7535，两笔时间均检查；7577 保留 canonical facts/evidence；7778 防止后报告覆盖早事件。
- 取消正文只阻止确认本次实施，不变成“本住院无输血”的医学断言；多事件必须逐事件绑定，不能因一条取消否定其他真实事件。

建议未来代码独占边界：TC02 owner 只触碰 backend/app/services/luxian_0609/native_extended_document_execution.py 的 070 分支及 _070_document_refs；新增专用测试文件 backend/tests/unit/test_luxian_0609_tc02_performed_event_contract.py。若要改变 native_transfusion_execution.py 共享时间 helper，须另行协调，该 helper 不属于可盲改的 TC02 独占范围。本轮未创建该测试或修改任何代码。

## 其余继承项

TC01：native_transfusion_execution.py:2865 以正文长度兜底确认实际输血，计划/拒绝/暂缓残留。需要受控语义实施事实，下一批单独处理。
TC03：同文件 :2388 术中正向模式把“术中未输血/备血”当实际事件；需要术中事件及行动归属。048 的 b4a98783e 配对/单位/合同修复已关闭并须保护，新触发残留未关闭。
TR044：pretransfusion_assessment.py:184、287 只取第一输血时间；多事件关联未关闭。db4bddb67 的合法 gap/矛盾状态事实合同已关闭，不能整条重新开或整条全关。单笔申请能否覆盖多袋/多次需业务口径，不能凭计数推定缺陷。公开脱敏验收出处 apps/medqc-web/docs/acceptance/2026-10-08-isolated-qc-integration.md:18、32。

资料范围事件：曾一次过宽 docs 搜索误返回非目标历史未脱敏材料，已停止；不保存、复述或传播该内容。本包只含合成输入、明确工程源码和既有脱敏报告。

