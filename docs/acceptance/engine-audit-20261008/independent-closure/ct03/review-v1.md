# CT-03 固定提交独立有限复审

结论：固定提交 `25406df7d2506f4870674ca73cddd10523bf966d` 的 CT-03 空/不可用讨论正文误判 C 修复通过有限工程复核，未确认 CT-03 新增阻断。原冻结 28 组中 27 组通过，1 组仍失败，明确为既有未闭 CT-04 公共 NA 合同问题；不能据此宣称本规则或全引擎全部通过。CT-01、CT-R02 和临床语义验收仍开放。

目录 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。独立冻结 SHA256 `c92061e62c1d0049f4d68ea007e774cb43ef54c81672289dba78134afe29ad9e` 不变。完整四个生产文件 diff 已静态阅读；执行时六个提交路径均与固定提交字节一致，前后 SHA256 无漂移，明细见 observed-v1.json。未修改生产、共享测试、owner 测试或任何冻结。

| 覆盖 | 具体观察 | 结论 |
|---|---|---|
| 已定位讨论正文缺失/不可用 | B01-B10 缺键、None、整数/小数、bool、list、dict、空串及仅空白全部 data_gap/required_field_missing。kind 为 uncertain_diagnosis_discussion_body_gap，成熟强时间保留，discussion_count/body_gap_count=实际行数 | 通过 |
| 多空与元数据不能补正文 | B11 两行、B12 三行均 gap 且计数对应；B13 record_content 缺键、另有 title/signature 仍 gap；没有对非空纯标题/签名正文作语义判断 | 通过 |
| 无 ID 不伪造定位 | B14 保留实际 discussion source snapshot SHA，material 能按实际来源读到该合成行；没有伪造讨论 ID。带合法 ID 的正文缺口场景，原生引用包含实际读取的讨论 document ref | 通过 |
| 旧行为保护 | P01 无讨论行为旧 NC；P02-P04 短/trim 后非空正文为旧 C；P05/P06 空与可用正文混合双顺序保持 C，discussion_count=2；P07 非空计划文字只保护旧路径，不闭合 CT-01/N10/CT-R02 | 通过 |
| 优先级与混合缺口 | T01 仅缺时强候选保持 CT-02 pure time gap；T02 成熟 local 仍 scope uncertain；T04 成熟强+缺时候选+空正文为 body gap，同时保留成熟时间和两个缺口计数 1；T05 同组合可用正文保持 C；T06/T07 来源/入院缺口原优先级不变 | 通过 |
| 文案及 structured_suggestion | body gap 建议为核对源系统正文及同步，不催补/倒签；无“医生未写/未见讨论/已完成讨论”假结论；混合时间缺口另说明权威时间核对，专属建议未被通用建议覆盖 | 通过 |
| 公开合同 | 61 组：body kind 与 body+time 混合 kind 仅 data_gap；缺必需字段、非法成熟时间列表、零/负/bool/小数/字符串/null 计数、行数与正文缺口数不等、矛盾 kind/摘要严格拒绝；3 私有字段仍按旧 sanitizer 过滤无透传 | 通过 |
| CT-02 保护 | 对原 28 组及 local/缺时补充两组再次执行，30/30 满足原状态、原因、kind、成熟时间与计数预期 | 通过 |
| 完整基线差分 | 12 组正常保护与旧路径对基线 81fe 的完整 native/renderer/finalizer逐字段比较 status/reason/facts/findings/suggestion/evidence，均一致。其中 T03 在两版本同为 technical_error，差分一致不代表其业务正确 | 通过差分；T03 业务仍失败 |
| 新实例保存回读 | B09 纯正文 gap、T04 body+time 混合 gap、P05 mixed C 分别新 SQLite、新 engine、新 Store 重新读取，状态、原因、facts、文案、建议一致。独立成熟病程来源/时间/field_path/原合成摘录及安全非空 source_ref 断言通过，原 ID 未透传 | 通过 |

既有 CT-04 保留：T03_before_seven_days_plus_empty_discussion 业务预期仍 NA/trigger_absent_complete。实际 native/reduced 为该 NA，公开 Finalizer 为 technical_error/model_invalid_output，facts/findings/suggestion 为空。基线与固定 CT-03 提交均如此；不是 CT-03 新回退。原 28 冻结未改、用例未过滤。下一 CT-04 独立附录已准备，等待正式修复提交与授权槽。

保存证据的实际字段：B09 空讨论卡只含 source_type=diffcase_discussion_record、真实时间 2026-06-09 09:00:00 和 HMAC source_ref，不造正文摘录；成熟病程保留 2026-06-08 09:00:00、field_path=record_content、摘录“目前诊断仍不明确。”。T04 另保留无时间病程的实际摘录及安全源锚，不补 record_time。P05 mixed C 只有既有成熟病程精确卡，discussion_count=2，原生 fact_refs 保留既有来源锚；不提供逐份讨论精确卡是既有投影能力边界，不应把证据形状归一误报为新丢失，也不据此改共享 projector。

执行边界：仅合成资料，sqlite 限定防护、.env 读取防护、网络/model 调用阻断均无触发；PG、真实模型、env 读取为零。未跑 owner 全套 218 或开发测试，开发通过数只作线索。主链 fixture 来自旧合成构造函数的 AST，不能代替真实源适配、真实脱敏病例全链路或浏览器/临床验收。首启动只因自有 utf8-sig 编码别名错误在读取冻结前终止，修正为 utf-8-sig 后完整单轮通过执行；没有产品修改。

出处：expected-v1.json、scenario-observed-v1.json、observed-v1.json、probe-v1.py 及三个合成 SQLite 均在本目录。测试槽已释放，无运行进程。
