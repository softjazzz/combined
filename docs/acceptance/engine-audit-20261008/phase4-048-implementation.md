# 048术中实际动作与事件归属候选 v1

> 最新状态：第三候选最终回放仍有错误临床结论，已停止当前048修复方案，未集成。本文件后续15/15等记录均属中间版本，不能当最终通过。

最终严格Schema版本15例协议/gate全部ready，但正式回放14/15：048_cancelled_plan_then_actual应C而NC。第三文书的actual_action引用夹带“原红细胞4U计划取消”，程序将该引用内4U与实际2U同时解析，另两文书只含实际2U，造成误报。逐字引用真实、Schema合法、gate为present均不能证明引用内全部剂量属于实际动作。第三候选失败后停止，未继续加提示词、扩否定词表或修改金标。

候选已完整保存于`.tmp/phase2-root-review/held-048-third-candidate/`（manifest包含各文件SHA，tracked-candidate.patch及完整候选源码）。048生产执行器、规则目录/预算及原生测试恢复到本批起点；新候选模块与专属测试移入该目录inactive，不在生产导入路径。没有删除文件、推送、部署或业务数据库写入。原048已知基线缺陷仍未关闭。

最终真实请求目录real-phase4-048-20261009T134357Z-1791553437794473600，15次14008 tokens；最终回放replay-phase4-048-1791553526990647800。下一步必须先重新定义可独立校验的动作—成分—剂量绑定；单个连续action引用可能同时包含取消与实际事实，不能再把片段内全部数字视为实际量。此方案仅记录，未继续实施。

独立复核另记录能力探测抛异常时尚未generate却计1call、隐私包装器bool转换弱化能力声明两个问题；候选已停，未另行修复或隐藏。

日期：2026-10-09；交接基线 `f6890063a`。本代理仅新增专属事实模块、专属工程测试和本文件；不改共享执行器、renderer、mapping、JSON，不运行pytest、模型、数据库或提交。AST语法检查两文件通过，不计业务/语义通过。

## 原反例及轮次

原三文书否定/仅备血输入、NA预期保留在 `.tmp/engine-audit-20261008/treatment-consultation/048-frozen-expectations.json`；MATCHED（C、2U=2单位）及TIME_CONFLICT（DG/association_failed）同样不改。现行 `_programmatic_048_status` 用正向术中输血词语和成分共现确认实施，继而整篇比较，把2U/4U/2U备用量报为实际量差异。

root核对 `next-batch/transfusion-family/review.json` 明确排除TC03修复，`treatment-consultation.md`/`tc02-handoff.md`标本触发为新残留；旧b4配对修复仍关闭。本批允许开始首个有记录TC03实现，历史未知不写为0，不重置已知轮次。尚无本候选执行结果；同根因最多3轮失败，主代理统一记账和调度单一验证槽。

## 专属文件与接口

- `apps/medqc-web/backend/app/services/luxian_0609/intraoperative_transfusion_fact_extraction.py`：IntraoperativeDocument(ref/source/body/trusted_operation_key可选)；`extract_intraoperative_transfusion_facts(documents, client, *, max_prompt_bytes, max_completion_tokens, event_time_parser)`；`intraoperative_gate(documents, facts)`。
- `apps/medqc-web/backend/tests/unit/test_luxian_0609_intraoperative_transfusion_fact_extraction.py`：人工事实协议、同材料引用、完整覆盖、未知、同事件时间/可信键、多动作、非法协议/计量、预算零调用保护。测试不声称模型判对否定/备血。

每文书语义事实为present/absent/unknown；present保留多个实际动作连续引用及各自事件键。动作必须实际发生且属于本次手术/麻醉过程；计划、否定、备血、其他住院阶段不算。absence要求coverage=complete完整覆盖声明，unknown不改absence。模型只返回连续唯一原文字符串，不数中文坐标、不生成关联ID；程序在原文及脱敏发送正文同时核唯一定位，拒绝占位引用。实际时间引用必须在该动作引用范围内且唯一，调用者程序解析；可信operation key只来自调用者真实已关联字段。重叠动作引用拒绝，防重复累计剂量。三文书存在但动作关联不能证实时保留DG。

完整prompt按UTF-8 bytes核显式预算，超限 `candidate_scope_incomplete`、0调用；无正文保留资料不足；无client或调用异常为 `model_transport_error` 技术失败，协议异常为 `model_invalid_output` 技术失败，合法unknown为语义未定DG。一次调用，禁重试，复用已有 `_json_response_object`/`_usage`，兼容正式client content/choices及完整JSON代码块、拒绝布尔/负计量，协议失败保留已有效解析计量。预算由root当前权威client/reader配置提供，不从病例ID、正文长度或其他规则搬魔数。

## 给root的精确集成方案

1. 048进入住院bloodtrans gate之前单独分支。完整读取三批准来源与真实状态/truncated；reader错误保持technical_error，不可用/缺失/截断保持DG。不得凭住院其它阶段已输血证明术中实际实施。构建document_ref必须来自真实snapshot选中材料坐标，不能只用重复业务ID。
2. 完整正文保留原字段拼接顺序，不截断。trusted_operation_key仅传现有可信手术/麻醉事件关联；没有这样的字段传None。event_time_parser可调用现行 `_parse_document_datetime`，成功返回标准ISO时间，不能由模型返回标准时间或自报同事件键。
3. 调用专属extract并统一加计量。非ready保留原reason；ready后gate非present直接按状态返回，不能再跑原正则。NA事实只声明已核来源、明确没有实际术中动作，不输出比较矩阵、实施true或量差异。
4. gate=present时只投影实际动作到既有比较器。每source的row保留原document_id与可信关联字段；**删除原surgery_process/anesthesia_process/record_content/assembled_text等正文优先字段**，content仅为 `'\n'.join(fact.actual_quotes)`。不把整篇原文合回去；否则备用/术前/术后量会复发。三文书多行暂维持旧association_failed范围，不静默挑一行；每文多动作完整保留。既有比较器继续处理紧邻成分剂量、单位归一、实际时间冲突与逐项数量比较。
5. typed事实/实际selected refs引用原完整材料，不引用派生影子行；投影仅服务已有比较器。root补齐renderer/mapping新的失败理由，不能输出医学缺陷文案来掩盖协议失败。

## 尚待主代理验证

先运行专属协议测试，再原三例正式048→binding→Finalizer终态。真实模型语义保护须至少覆盖否定仅备血、肯定含无反应、备血与实际量混合、术前/术后实际但术中否定、跨手术/跨麻醉事件、未知归属及同文多个实际动作。原输入和预期冻结，新增保护单列，不把人工协议绿替代真实语义正确。

严格关联需要实际时间或可信手术键；旧无时间且无可信关联材料可能由C变DG，须单列真实保护结果而不能静默改oracle。完整输入容量和输出预算真实能力、最终refs、正式任务/API/UI链仍未验证。本文件不宣布048规则关闭。

## 集成与独立复核后的修订

代理随后获授权接入native执行器及既有组合测试。048仅以完整三类术中文书核对，不再经过住院bloodtrans/mr实施门控。标题/方法名不能替代临床正文；明确实际但缺剂量保留present交程序判资料不足。缺失/未知不输出“已确认术中输血”的文案。未改044/045/046医嘱触发合同。

独立复核发现逐action事件时间丢失后，旧比较器可能因句界重解析失败，把不同时间的量合计抵消。现IntraoperativeFact保留event_times，与可信operation key分开；validated_actions_by_source把每个原文动作及程序已核时间传入旧单位/剂量解析，逐动作核对，不再由96字符邻近窗口重新认定时间。多动作任一缺逐次时间为DG，单动作有可信同手术键且无时间的兼容C保留。正确配量、交换量与缺时三个回归已通过，独立复核确认原P1消除。

原生输血128项、专属协议22项，以及合同/展示/Finalizer/关联保护在主代理边界组700项均通过。旧组合测试中占位文书原NA改DG，是新事实未知合同；完整术中空源不再受无关住院mr读取错误影响而NA。原文本均保留，临床历史反例预期未改。

048首轮真实模型15次15967 tokens：13项gate符合，2项模型协议TE。其一时间未包含在动作原文中；另一在JSON前附说明。严格解析未放宽，提示明确时间必须随连续动作引用、最终仅输出JSON。首败目录real-phase4-048-20261009T133314Z-1791552794428825000保留。正在进行后续单槽验证，后续结果见主代理最终记录，不能将当前报告当全规则验收通过。

## 主代理真实响应验证

第二轮15次16035 tokens：15/15事实gate符合，无TE。目录real-phase4-048-20261009T133547Z-1791552947539502800。严格原请求hash核对的native→binding→Finalizer响应回放15/15最终状态符合，引用限本次session真实source/document refs；回放目录replay-phase4-048-1791553092840417100，无新增网络调用。

两轮30次32002 tokens；首失败保留。另独立新增phase4-048-event-expectations.json的3例逐事件压力保护，冻结SHA e44bef4528124d5387924498d6498687dd51baea99445ba7a5ebb16d5da67368，不改变原29gold。真实客户病历覆盖、三文书多行复杂关联、来源/模型容量上界以及完整应用/页面验收仍分开记录，不能因15例通过宣布整规则完成。

## 逐事件真实压力测试首败

3次3688 tokens；同一手术两次输血的匹配/交换剂量两例，模型在术后首次病程的明确术中回述上返回unknown，gate为DG；缺时例按预期DG。局部gate仅1/3符合，不能将此组记通过。首败real-phase4-048-events-1791553098281322900保留。生产程序未把这些未知判C；本轮针对文书载体与动作阶段的区分，补充通用提示：术后记录可明确回述术中实际动作，文书类型本身不决定动作阶段，不按病例ID或新词表消除unknown。

逐事件修订复测3次4066 tokens，3/3gate符合；保存真实响应正式native→binding→Finalizer回放3/3最终C/NC/DG符合。新目录real-phase4-048-events-1791553167829001600，回放replay-phase4-048-1791553201778529500。原失败3688 tokens留档，不用新结果覆盖。最终提示版本补充回述语义后，原15例另做一次回归，结果在最终汇总中记录。

## 输出协议第三候选

最终提示版本复跑原15例时为14/15 ready符合、1例TE（TIME_CONFLICT在JSON前夹分析），15次17428 tokens，目录real-phase4-048-20261009T134008Z-1791553208841457500。该结果不得以之前15/15覆盖；也表明纯提示词约束不稳定。

第三候选使用现有正式client的supports_strict_json_schema能力声明；仅明确支持时发送严格JSON Schema，约束文书数量、受控alias、必填字段及禁止额外字段。每次enable_thinking=False、禁止回退重试；不按模型名或病例名做分支，原引用/来源/事件校验仍保留。不支持严格Schema的客户端保留同一严格本地解析，失败TE。新增4项协议保护后，原生及协议154项通过。真实请求快照逐次记录request_kwargs与能力声明，回放要求完全一致，不把环境中thinking_budget=256误称本次仍开启thinking。

若第三候选真实验证仍失败则停改，不再叠加提示词或静默重试。
