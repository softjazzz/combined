# 第二轮出院与术后五规则独立审查

日期：2026-10-07。代码基线：`c3a87a4f820259bca37a01764522ea1f3f485a3c`。检查时 HEAD 一致，所涉执行器及出院病程模块无工作区差异。CodeGraph 首次调用失败（unable to open database file），随后按源码定位。

本轮确认 **2 个合成工程缺陷**，均有正常对照，经正式 native 执行器、绑定/reducer、Aggregator 输出复现。没有确认真实病例误报，不宣称五规则临床验收通过。达到两项缺陷交付条件后停止扩展。

## 范围与方法

按规则总表 qc_point 审查：

| 规则            | 质控点                                 |
| --------------- | -------------------------------------- |
| LX0609-08-01-03 | 出院诊断或死亡诊断错填、漏填、顺序错误 |
| LX0609-04-05-02 | 无术后三天内上级医师查看病人记录       |
| LX0609-04-05-03 | 无术后首次病程记录                     |
| LX0609-08-02-01 | 无出院前一天或当天的病程记录           |
| LX0609-08-02-02 | 无上级医师同意出院的意见               |

仅复用旧清单的匿名别名/住院三坐标；重新读取六例 0910 的原始 CDM 来源。每次连接先 `SET TRANSACTION READ ONLY`，随后 `SHOW transaction_read_only=on`，结束 rollback。没有读取历史规则输出来决定预期，没有模型调用、数据库写入、生产修改、提交、重启或推送。

原始来源与预期在私有目录保存；预期冻结时间为 `2026-10-07T13:29:17.690322+00:00`，包含原始文件 SHA256。工程预期在执行前冻结。真实病例预期保留初稿，不回填成执行结果；下述不完整审阅明确不计通过率。

## R2-DP-01：无时间的上级查房被误报为缺少查房

- 优先级：P2。规则：LX0609-04-05-02。
- 条件：一台有明确结束时间的已实施手术，72 小时观察窗口成熟，上级查房来源可读且有一份实质正文，但 record_time、record_datetime、submit_time、submit_datetime 均缺失。
- 冻结预期：data_gap。无法定位既存查房是否处于窗口，不能断言窗口没有查房。
- 实际：`non_compliant / required_document_missing`；Aggregator 保持相同状态。
- 正常对照：给同一记录补入术后一天记录时间，返回 `compliant / requirement_satisfied`。两例模型调用均为 0。
- 根因：`backend/app/services/luxian_0609/native_extended_document_execution.py:3620` 按 `_row_time` 过滤后，将没有匹配时间直接作为 unmet；没有把无权威时间的既存查房保留为资料不足。
- 真实范围：六例原始材料的手术结束时间均缺失，当前先被该门禁挡住，未在六例中观察到此误报。该问题是已通过正式链路的合成机制，不是患者已发生错误的证明。

## R2-DP-02：带姓名的纯签名被当成出院前病程正文

- 优先级：P2。规则：LX0609-08-02-01。
- 条件：已出院，窗口内仅一份日常病程，正文仅为合成文本“医生签名：张医生”。
- 冻结预期：data_gap，无法确认临床病程正文存在。
- 实际：`compliant / requirement_satisfied`，`course_present=true`；Aggregator 同样合规。
- 正常对照：同一时间、同一来源改为“患者病情稳定，明日出院。”，返回合规。两例模型调用均为 0。
- 根因：`backend/app/services/luxian_0609/extended_document/discharge_course.py:12` 只排除四种完全等于无姓名签名标签的文本；姓名、职称等后缀会使纯签名通过 `_has_course_body`。
- 真实范围：六例中存在纯签名标签材料，其不带姓名形式被正确挡为资料不足；没有确认本轮六例发生带姓名纯签名误放。不要把合成后缀反例计为真实病例缺陷。

## 六例原始材料与离线对照限制

| 匿名病例 | 063 出院诊断  | 065 术后上级 | 066 首次病程 | 067 出院前病程 | 068 同意出院 |
| -------- | ------------- | ------------ | ------------ | -------------- | ------------ |
| C01      | non_compliant | data_gap     | data_gap     | compliant      | compliant    |
| C02      | non_compliant | data_gap     | data_gap     | compliant      | compliant    |
| C04      | non_compliant | data_gap     | data_gap     | compliant      | compliant    |
| C05      | compliant     | data_gap     | data_gap     | compliant      | compliant    |
| C09      | data_gap      | data_gap     | data_gap     | data_gap       | data_gap     |
| C12      | non_compliant | data_gap     | data_gap     | compliant      | compliant    |

这些是原始 CDM 行装入 EvidenceSession 后的正式 native/reducer 离线结果，**不是本次正式 PG 任务结果**；未走全量 provider 查询装配、保存/API/UI，不能用于声称页面已更新。对手术来源保持其实际缺失值，没有补造结束时间。

预期初稿的局限：066 五例因看见首次病程正文而初拟合规，正式代码要求手术结束时间与文书权威时间安全关联，来源缺失使其 data_gap；不能直接把这一差异当缺陷。C02 的 068 初稿只关注 record_time，未充分核查 submit_datetime 兼容时间，故其差异也不作为错误。C04/C05 的角色意见绑定未完成盲审；063 存在同义名称/诊断串，未冻结临床一致性答案，不能把字符差异直接升级为临床误报。C01 多份手术文书与单份首次病程的关系尚需原始业务复核。重复出入院未覆盖。

另在同一工程探针观察到 065 对窗口内纯签名标签也判合规，作为存在性检查薄弱的补充现象保存，不增列第三个确认缺陷。

## 可复核产物与执行

私有目录：`.tmp/0910-full-audit/round2-discharge-postop-private/`。含原始六例、冻结预期、工程输入/输出、实际六例回放与脚本；均不提交。长期文档不含患者原文或三坐标。

执行：`python -X utf8 .tmp/0910-full-audit/round2-discharge-postop-private/replay-private.py`。其调用项目测试夹具建立合法 snapshot/materials，再调用正式执行器和 reducer；工程反例另经 Aggregator。最终 5 个工程探针、30 个真实来源规则回放全部调用量 0。初次合成 mr_surgery 时间用了字符串，被类型门禁挡为 data_gap；后改为该来源正式合同的 datetime 后才确认缺陷，原始病例来源没有随之改写。

本轮仅审查，未改修复代码或新增产品测试，未运行全量回归。
