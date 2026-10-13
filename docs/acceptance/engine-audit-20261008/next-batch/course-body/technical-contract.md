# N10 最小技术合同草案（仅决策准备）

范围仅 LX0609-04-05-02/065、LX0609-08-02-01/067。读取起点根 ref 为 2d66663b632efa5543809109fefff48bea5e283d；收尾 ref 已推进 0683dfb9e0c407e6b9ad38a48cad2a0ec6649d32。此次为源码读取时点哈希索引，非 git show 固定 blob 验收；文件哈希见 JSON。没有生产导入、测试、Git 命令、网络、env、PG 或模型调用。保留原 preparation/evidence-index/minimal-candidates，不改冻结输入，不宣称修复。

## 结构证据边界

能证明的是：当前可见资料不能完成原反例的结构闭环；不能证明所有潜在源资料都不存在独立字段。reader:253–279 允许独立 title/time/author，1569–1583 仅投影实际存在列。公共 round6:74 只记录正文与结果，没有完整原冻结 row。公开 test_n10_course_template_body.py:_run 有 title/time，没 author，但它只包含旧20项，不包含两条残留；不能借该夹具替代原反例。姓名例缺独立 author 证据，时间例缺原 title/time 精确对应证据。仅基于当前资料，零调用结构修复不足以关闭原两例；未来若取得合法脱敏原元数据可重新判断。不从正文捏造 title/author，不补关键词。

## 最小事实与范围

唯一语义事实 clinical_body 表示本材料已有临床正文，不评价长短、充分性或医师资格。原两空壳期待 absent，病情稳定/标题后真实正文/医生签名:继续观察。期待 present。只抽正文事实；事件、死亡、时间、72小时、出院窗口和最终状态仍由 Python 判定。

抽取单位为同快照 source_key + occurrence material_ref 的原行正文；使用内部别名，不发送原 document_id/患者/医师标识。每行独立，不凭 eventID/相同标题拼正文；absent 覆盖该行完整受控正文，不冒称覆盖一份可能尚未完整读取的实体文书。跨行“无正文”结论要求候选材料全部可读、来源 complete、未截断且每行均 absent。来源 unread/truncated 沿既有失败优先返回，不做抽取。

按既有 Python 时间窗口选择候选，不让窗口外 unknown 污染结果：065 为成熟事件72小时窗口内及可能相关无时候选；067 为出院日/前一日及无时候选。不得为减少容量丢掉相关行；所有原行 refs 保留。不新增 SQL 字段或缓存框架。

## 回执与引用

JSON 恰含 schema_version、documents；每项恰含 document_ref、clinical_body。atom 恰含 state/span_id/start/end/quote。present：同一材料 span，零基左闭右开坐标，非空逐字 quote；absent：span/quote=null、start=0、end=整份受控 body 长度；unknown：四个引用字段均 null。拒重复键/重复或漏别名/额外字段/跨文书引用/越界/截断 finish reason。全范围坐标只能证明覆盖声明，不能证明模型语义正确。

复用 native_preop_content_execution._document_spans（230）保留全部字符，以及既有受控抽取的同文书引用校验/受控 client/脱敏 guard；不复用麻醉业务字段或 Prompt。验证的坐标属于正式脱敏后的受控 view，不能无转换当作原患者正文坐标。客户证据沿真实 material_ref → Canonical → Envelope 安全投影，只显示允许来源、字段、时间、片段；原 ID/Prompt/模型回执不公开。067 保留 _selected_course_document_refs:486 对缺ID/重复ID的拒绝精确映射，不回退整源作为客户文书；模型不能替 Python 修补映射。

## 调用预算与归约

当前两个合同均 native_async/program_only/max0/v1、目录 prompt_version=none。拟仅这两项改 program_then_optional_llm/max1/v2，并各自登记新的事实 Prompt 版本；其他条目完整比较不变。每规则最多一个受控批次；同时选065/067最坏两次，不借共享调用隐去计量。不增客户端选择/传输重试；抽取层无重试，allow_length_retry=False。计 logical attempt 与 HTTP delegate 分开。

零调用：既有结构门控已决定、无相关候选、空白字符串或已有 helper 确认纯格式行。非空自由正文（含短正常）从0变最多1；无client/模型失败不得按旧字符串非空放行为 compliant。拟复用容量8原行、6000字/行、12000总字、4096 completion tokens，原行容量先检查，不截断/去重后绕限；超过返回 gap/candidate_scope_incomplete。容量是安全边界而非临床充分性门槛，须列入变更保护。

合法完整回执：一份相关 present 足以满足067；065逐事件有 present 才满足该事件，不被其他 unknown/无时行遮挡。无 present 且有 unknown → data_gap/semantic_extraction_unresolved；仅窗口内 absent → 保留 data_gap/required_field_missing。真正来源无候选、迟到、成熟度与缺权威时间保留各自既有状态/优先级，不由模型改判。065不成熟事件不因正文unknown额外改成gap。不可读或未提供正文不是 absent：单行未知不能否定另一有效 present；仅它一行时保留原 required_field_missing 保护。非法整个回执不能局部信任伪 present。

模型失败/unknown/容量不足不是医生缺项：missing_fields/missing_sources为空，不要求补写、倒签或改写；可建议复核现有材料/重试。新三态回执不新增交付 uncertain/technical_error。

## 文件责任与 TC01 冲突

拟新独占小模块 course_body_fact_extraction.py、专属 test_n10_course_body_controlled_facts.py/doc；不是现在授权实现。直接共享消费点：native_extended_document_execution:3898/3920（065），discharge_course:98 + native:4197（067）；原 helper:13保持格式责任，新增语义走两规则适配，不扩大064/066/068。native、helper、两条 extension 合同与目录必须 root 分配 owner。

TC01 正独占 customer_renderer.py/canonical_result_finalizer.py；N10不得碰。后续需其 owner 加065/067新失败的窄 tuple：renderer 的 Finalizer message/structured reason message及 structured_suggestion 保留分支；Finalizer 的 _RULE_DATA_GAP_EXPLANATIONS，确保不回落“补资料/补写”默认文案。现语义失败特例为037/055，065/067尚无对应 tuple。不得扩大通用 Finalizer 判定或使用临时reason替身声称正式链通过。

## 原保护与下一批决策

original-protection-index.json 仅索引原测试/公共报告/四候选，不覆盖预期。保留两残留、旧20格式及短正常、065有效+无时/签名行、缺时间/迟到、067签名/真实正文；再冻结unknown/非法回执/上限/原refs及客户文案三态正式链。原测试运行及真实语义本轮均未验。请 root 决策调用合同与共享文件时序；在TC01释放或其owner交付窄支持前，不能宣称N10完整工程闭环。
