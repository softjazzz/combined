# 020/023待处理事实复核

本次仅检查用户指定排障包的冻结模型响应和当前episode生产主链，并执行人工合成反例。没有请求模型、读取数据库或保存患者正文。旧任务保存状态未修改。

## 原包证据

020为data_gap/candidate_scope_incomplete；023为uncertain/semantic_low_confidence。三个建议的冻结模型标签分别为generic_trace/medium、specific_trace/high、no_trace/low；重复响应中的最后一项仍为no_trace/absent/low。全部调用已返回，023并非网络未完成。

原包展示specific 1、generic 1、missing 1仍保留逐建议事实。**这些计数不能解释为三项均已确证：generic标签只有medium置信度，missing还受到病程来源完整性约束。** 当前仍有带正文却缺时间的上级病程，不能以未在已定时候选中找到记录推断完整资料内不存在记录。

## 当前复核归并合同

`native_consultation_episode_execution.py`的`_merge_rechecked_execution_assessment`优先采用复核high结果；否则只有原结果及复核均为no_trace、absent，且两次trace_refs与execution_refs均空时，才将复核结果置信度提升为high。两次generic/medium不会因此提升。

调用方按非high建议筛选复核输入，返回结果按recommendation_ref归并；没有进入复核集合的high specific保留原对象，不会被重复响应改写。复核解析器还校验预期建议集合及引用，因此不能凭额外输出改写未投递建议。

限制：merge函数本身不校验两对象的recommendation_ref相等，依赖调用方按同ref配对；“两次一致”只指上述状态与空引用条件，并非独立真实性验证。重复同一模型判断仍可能具有相关错误，不能将置信度提升当成临床证据增加。原包第二次响应包含全部三条建议，与当前缩小复核输入的实现存在差异，不能宣称原任务逐行执行了当前版本调用方。

## 可运行离线证伪

在backend目录运行：`python scripts/audit_consultation_020_023_pending.py`。

- 020确定缺失加另一项未知，仍不合规；明确痕迹加来源缺口仍可合规。
- 020缺失加病程来源缺口保留数据不足；仅辅助检查来源缺口不否决该缺失结论。
- 023高置信笼统记录加未知项，仍不合规；中置信笼统记录加高置信具体记录，仍待确认。
- 同时验证一致no_trace/absent提升、状态不一致不提升、generic/medium不提升以及未复核specific保留。

结论限于当前状态映射与归并行为；不证明原病例建议确实已执行或确实缺失。条件性与未来建议的触发合同仍缺显式字段，本病例尚无证据证明由此误判，不在本次扩大修复。

## 主协调原包回放补充

原任务冻结截止9月9日，同一包的Provider→当前episode执行器→binding→Finalizer，回放包内3条已有模型响应，网络调用为0。复现020=data_gap/candidate_scope_incomplete、023=uncertain/semantic_low_confidence；三个标签计数仍为specific1/generic1/missing1。该验证仅证明捕获响应在当前链路的投影，不是新的模型判断或临床真实性验证，也不代表新任务出院截止场景。

020最终customer_evidence为0，023为7；逐建议事实引用与最终公共定位需区分，不声称全部定位已解决。本轮未修改020/023生产代码。未来/条件性建议口径与低置信标签展示仍是后续风险，未证明当前原病例因此误判。
