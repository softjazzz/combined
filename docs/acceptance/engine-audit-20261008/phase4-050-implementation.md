# 050事实模块实施准备

日期2026-10-09。基于root派发HEAD `f6890063a`，本owner仅新增诊断范围抽取模块、协议测试及本记录；native接线、共享合同、Renderer/Finalizer由root维护。使用Code技能的计划/实现/验证顺序；已获并发模块实施授权。不改冻结的`phase3-050055-expectations.json`。

## 接口

`extract_diagnosis_scope(documents, llm_client, *, max_prompt_bytes, max_completion_tokens)`只读取每行`record_content`（缺省兼容`content`）正文，以输入顺序生成row_index。输入记录ID、病例ID、时间及其他字段不发送给模型，也不参与语义判定。

结果`DiagnosisScopeResult`字段为state、documents、reason_code及llm_call_count/prompt_tokens/completion_tokens/total_tokens/api_time。state为ready/data_gap/technical_error。documents为严格逐输入行覆盖的`DiagnosisScopeDocument(row_index, coverage, assertions)`，coverage为complete/unknown。合法空assertions只有complete才能表达该正文已完整核查且无相关事实；调用者仍须先证明来源完整、可用且未截断。空输入不提供来源完整性证明。

每条`DiagnosisScopeAssertion`保留scope（diagnosis/treatment_plan/local_problem/unknown）、diagnosis_state（explicit/unresolved/undetermined/unknown）、polarity（affirmed/negated/unknown）、temporal_scope（current/historical/future_conditional/unknown）、association（explicit/ambiguous/unknown）、quote/problem_quote，以及程序定位的原文quote_start/quote_end/problem_start/problem_end。

模型只返回连续字符串，不要求模型计数中文坐标。quote必须在发送隐私view及原文分别唯一连续出现；因此脱敏前缀变化不影响原文定位。explicit问题提及必须在quote内唯一出现，程序用原文span生成局部键；不接收模型问题ID。ambiguous/unknown不输出problem_quote、不猜owner。上下文quote允许重叠，支持同句多问题；七个事实字段完全相同的重复项无效；同一quote/problem_quote允许保留不同状态，避免整句多问题信息被协议消除。若引用涉及脱敏替换或重复原文无法唯一定位，报输出无效，不凭索引/几何关系确认问题身份。可由模型引用更完整上下文消除重复，但不会自动拼接或改写引用。

## 程序消费约束

模型不算入院天数，不裁定讨论存在性，不输出C/NC/NA。root使用可信入院/文书时间判断7天成熟。肯定、当前、诊断未明确或治疗方案尚未明确的可核事实可证明触发存在性；不能用另一已明确问题或另一份病程抵消。local_problem或未知范围保留现有未决边界。

冻结预期`050_plan_difficult_current`要求治疗方案难以明确也可触发；不能缩减为整体诊断关键词。`050_ambiguous_problem_owner`明确至少一问题当前未明确，即使不知道是哪项也不能消除存在性；关联未知不表示该未明确事实不存在。历史与当前各自保留，模块不建立历史问题到当前解决的跨陈述/跨文书关系、不以模型自报ID关联。只有调用者可证明同文同问题关联时才允许历史已解决排除；无法证实时保持未决。逐字引用校验不能证明模型医学语义正确。

## 容量与失败

来源正式日常病程上限200行、讨论50行，来自`bundles/assembly.py`；模型容量是独立层。root指定运维预算65536输入UTF-8字节、16384输出token。输入超max_prompt_bytes零调用返回data_gap/candidate_scope_incomplete；不将其冒充真实source_truncated。没有截断、分批或隐藏重试，单次generate显式`allow_length_retry=False`。

本模块未伪造每正文问题数或全200行输出上界。现有数据合同没有每文书多问题输出基数上限，因而无法保证16384token覆盖任意完整200行源；输入预算内也可能因输出截断失败。只接受finish_reason=stop、完整逐文书索引覆盖及严格schema；length、漏行、重复/额外索引、坏引用、重复JSON键、usage缺失/不自洽或completion超过预算均technical_error/model_invalid_output，清空所有局部事实，保留已观测usage。完整覆盖的语义unknown是ready事实，不伪装为传输/来源错误。模型声称complete仍须独立语义验收，不能凭协议校验证明未漏临床问题。

正文不可读为data_gap/required_field_missing。无客户端/调用异常为technical_error/model_transport_error。正式source_unavailable/source_truncated由调用者读取来源时处理，本抽取模块不猜来源状态。未知/关联歧义由root按存在性及规则合同消费，不统一映射DG。

## 验证与轮次

新增协议测试覆盖原文定位、两种响应包装、usage、同句多问题重叠、关联歧义与已知存在性、治疗方案枚举、否定/未来/历史事实保留、完整空与未知空区别、文书索引/字段/重复/引用保护、隐私前缀坐标、输入byte边界、缺正文与传输错误。它们使用人工协议替身，仅证明程序合同，不证明真实模型语义。未修改冻结金标，也不根据病例ID或正文关键词生成期望。

生产接线和pytest/真实模型/数据库/提交均等待root单一测试槽。静态编译可做。初始模块交付尚未经执行验证；后续失败与修订按本节及主代理验证报告追加，不能以初始静态状态重置轮次。每个经root授槽的实现验证记录源码hash、原反例/保护、结果及失败原因，同根因最多3失败轮，第3轮立即停改报告，首失败不得覆盖。

## 首次真实模型协议失败修订

root首次050真实抽取14例为12项ready及2项technical_error。首失败保留在.tmp/phase2-root-review/real-phase4-050-20261009T132652Z-1791552412844723900。一项非explicit关联仍填写问题引用，维持输出无效并强化提示；另一项同一连续上下文分别表达已明确与未明确，被旧quote/problem组合去重过窄拒绝。现改为七字段完整事实去重，允许不同状态共享上下文，仍拒绝完全重复项。明确diagnosis_state=explicit与association=explicit含义独立，ambiguous/unknown必须problem_quote空串。新增对应协议正反例；仅静态编译，未自跑测试/模型。首失败不隐藏，轮次不因协议修订归零。

## 主代理已完成的验证

050原生、协议、时间及缺资料闭环工程回归557项通过；另4项隔离临时SQLite保存及新实例回读通过（未访问业务数据库）。独立复核发现并修复未知explicit误NA、治疗方案展示不准确，以及早期病程不必要语义调用；程序现仅送入满7天或缺时病程，原索引显式映射，纯早期正文缺失/超大都零调用NA。

真实模型沿用qwen3.8-flash/alibaba、thinking预算256，仅合成资料。首轮14次13975 tokens：12项语义符合、2项协议TE；修订后14次15510 tokens：14项当前未明确触发语义均符合、无TE。两轮共28次29485 tokens，无隐藏重试。第二轮目录real-phase4-050-20261009T133034Z-1791552634795869000；原请求hash严格一致的native→binding→Finalizer真实响应回放，原4项最终状态4/4符合，新增10项仅冻结语义而未预设最终状态，仍明确列为最终gold未设，不计14/14全规则通过。

回放目录replay-phase4-050-1791552773317659300，证据引用均为本次来源/文书引用子集。独立工程替身和真实模型语义验证分开记录；尚未完成客户真实阳性/完整任务/API/导出/页面验收。原29冻结文件未改，SHA256为e2b23e24b634172aa2cc4bfd45f408e25d6ae43b162caa420a2c78d2dae9d449。

## 最终集成范围

048第三候选未通过，已撤出集成。050原生、协议、合同、Renderer/Finalizer和关联输血保护在最终集成版本1223项通过，另4项隔离SQLite已通过；候选048测试结果不混入这1223项。前端lint无错误，既有1286项格式警告未改动；本批无前端代码改动，按AGENTS最小门禁执行encoding及lint，不宣称全量UI/type-check通过。浏览器仍最后验收。
