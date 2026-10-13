# N12 固定 08a 独立复核

结论：接受限定离线工程闭环；固定 `08aed59db3ed9bf08316fc792a757a3ee65d992b` 未发现剩余代码阻断。此前“多个完整文书直接 gap”的 P1 已关闭。父 `1b973859d1f95c099745c8af7500c3e937c05772` 只引入解释支持（源 `195e20cf16402052acb4aff23f76234d144296f4`）。本报告不宣称真实模型语义或全面医学保护已验收。

## 独立执行证据

冻结 41 项独立核心输入与 2 项合成正式 privacy wrapper 预期，未调用作者43测试，也未使用支持测试临时 reason 白名单。全部 43 项状态/原因/事实/调用/Token/assertion 在首进程进入 SQLite 前完成。首进程最终退出1不是“全进程通过”：其 SQLite 证据比较采用了错误阶段接口，详细失败如下；此阶段没有独立逐项43 JSON，保留完整固定脚本、冻结输入及 first-attempt 控制流程记录。

独立状态覆盖原四空标签、正常有效阴性与相邻标签、多份同事件各自完整、多文书半套不能拼齐、同实际文书分段和结构分散、未知与 absent 同回执、非法引用/字段/JSON、来源不可读/截断、正文缺失/非字符串、原9行即便同ID仍超限、单6001、总12001及组后6001。实际加载 v3/program_then_optional_llm/1、Prompt版本及 definition 一致；新 reason 实际在 decision_model/reducer 内，没有替身。

追加三态正确阶段补测退出0，运行3.02秒：实际 native→Binding/Reducer→Canonical 得 compliant、non_compliant、data_gap；经正式 Envelope projector 保存磁盘，关闭写 Session/连接池，用新 engine、新 CanonicalResultStore、新 Session 读取，三态状态/原因/安全事实/建议均保留。每态3条安全 evidence，逐条对照冻结来源类型、record_content 字段、记录时间与完整短合成正文片段；投影证据列表严格相等，source_ref 为 HMAC 格式，原始文书/病例 ID 不公开。完整逐项补测记录在 sqlite-runtime-results.json。

## 判定与调用边界

四条原空标签的输入与缺项预期未改；Mallampati仍是旧 airway_assessment，不增加必填字段。正常及有效阴性保持 C。自由正文0→1、无client→gap是本轮显式工程合同变化，不冒称原NoModel/0全绿。

仅同来源、同明确 document_id/id 的分段可合并正文与结构；缺ID每material ref独立，不使用application/event ID合正文。不同实际文书各自核对且缺项并集；任一unknown优先gap。来源完整性、正文类型和原行8/6000/12000预算先查，组后再查，原所有refs保留；不靠分组缩数绕限制。同事件多个各完整 C、两个半套 NC、同doc分段 C 已独立执行。

新逻辑最多一次受控client调用，失败计一次、length retry禁用；成功固定Fake Token15，transport/guard拒发为0。已知合成身份残留在正式 wrapper delegate前被拒：logical attempt1、delegate0、真实HTTP0，最终 semantic_extraction_unresolved gap。正常无身份正文经wrapper再通用脱敏后坐标仍可用：logical1、delegate1、真实HTTP0。没有绕guard或读真实identity。客户解释是内容抽取待确认，缺源/缺字段为空，建议复核或重试并明确不要据此补写/改写。

## 原失败保留与存储合同补充

1. 首进程3.79秒，43项核心/wrapper断言完成后，SQLite NORMAL evidence断言失败：raw Canonical的 evidence 是说明字符串，正式projector把 customer_evidence 转成公开安全列表。原 frozen-expectations.json 未改。root接受这是审查阶段合同错误，不能删除证据检查或把退出1说成全通过。
2. sqlite-contract-supplement.json 另行冻结正式投影→读取比较与来源/字段/时间/片段/ID安全约定。第一次启动该补测脚本出现自有拼装SyntaxError（0.31秒，0导入/0新数据库），记录在 supplement-syntax-failure.json；按唯一错误片段修正且静态compile后，下一授权槽补测才退出0。

保留首次完整脚本 fixed_runtime_probe.py、原预期、first-attempt.json、补充合同、解析失败元数据与最终成功脚本/sqlite-runtime-results.json。没有修改生产、原预期或作者测试来追绿；测试槽均在进程退出后释放，报告整理不占槽。

## 必须保留的限制

旧25项NoModel测试在 calls==0 处失败，医学状态断言未到达，不能计作医学保护通过。作者277、43红绿与基线统计没有计入本独立结果。真实模型抽取正确性与真正通读全文未验：absent全文范围只验证输入覆盖声明，present坐标只证明同文书引用真实，不能替代临床语义。实际HTTP重试预算、真实PG/患者/identity provider、旧payload、发布/golden gate均不在本次验证范围，N10继续开放。

本次全程防dotenv/socket/httpx，无PG、真实模型或真实患者材料。
