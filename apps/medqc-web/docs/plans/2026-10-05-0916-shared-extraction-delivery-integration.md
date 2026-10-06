# 0916共享抽取失败交付受控合入

## 范围与依据

最终工作区为D:/LLM/LX888/apps/medqc-web，起点db340a11a。A验证树09bf7a826已经修复此缺陷，但最终D未迁入该部分；不得据A通过宣布D已通过。

主协调亲自核对D的_execute_record到_execution_to_record_outcome：抽取diagnostic只进入摘要，后者未接收该diagnostic，缺失模型事实的原生data_quality_gap仍被运输为正常结果。保存入口已有0916合同校验，问题不在重新定义临床状态。

独立反例使用现有合成SQLite/API链，固定首程结构字段、非法semantic_facts容器及两次合同重试。在db340a11a源码上，两正常场景通过，故障场景实际status=completed且failed_records=[]，与预期技术失败交付不同。证明来自[主协调基线产物](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-delivery-chain-baseline-v3-private.json)。前两版运行器未到业务断言，分别被环境文件防护和无效cache_clear调用阻断，保留为运行器故障，不计作产品反例。

## 最小方案

1. 共享抽取器仅在已选到可读来源且实际发生生成、响应、JSON、合同或接地异常时，记录本次受影响的requested规则号。没有材料不增加技术失败标记。
2. Worker只把受影响规则中缺模型事实的结果转入执行失败清单；既有来源缺口、年龄/叙述者门控、合法unknown与已成功原生结果保持。015/016和018独立族不借共享诊断改写。
3. 不改规则判据、资料可见性、Prompt、调用预算、005/006引用修复合同或发布门禁。抽取技术失败不得伪装成院方资料缺失或临床不合规。
4. 使用既有保存合同验证每个病例/计划规则恰好一个结果或失败，随后由既有A1比较层保留成功目标可比较。

生产文件白名单为semantic_extractor.py和batch_worker.py，测试仅本缺陷聚焦单测、必要的既有失败断言，以及test_rule_validation_0916_chain.py。不迁A的007/008事实合同或完整文件。

两个生产文件未越过Python2000行预警；新增逻辑仍属于现有抽取诊断和结果运输职责，不新增业务域、注册表、状态机或平台。主协调亲自审查跨层边界；规则执行器的临床结果不由保存/API重新判定。

## 验收与保护

- 各技术阶段、一次生成失败与最多两次合同重试；没有可读材料及合法unknown不误转失败。
- 已有来源/年龄/叙述者门控不因模型失败被遮蔽；015/016、018的独立族结果保留。
- 成功结果原生status、reason、decision_facts、anchors、evidence、findings、suggestion不被后层改写。
- 实际32条Worker、SQLite保存与合成API回读：29有效结果和3技术失败；成功010目标仍same；发布批准仍拒绝。该测试覆盖链路，但认证被合成替换，不证明生产认证、PG或页面验收。
- 最终提交版本与含005/006未提交实现的工作区分别验证，不能只测试脏工作区后提交另一份代码。

当前D的semantic_extractor.py含他人未提交005/006修改，另有他人文档已暂存。提交须隔离本修复索引内容，不提交或撤销那些改动；不全量暂存、stash、reset或推送。独立临床签认、上线批准、新PG业务写入和真实模型额度均不包含于此闭环。

## 执行记录

当前工作区235项聚焦保护通过（包含保留中的005/006实现），3种合成API场景通过。准备提交的隔离索引另做独立源码overlay验证：176项聚焦单测、相同3种API场景通过，不依赖005/006未提交实现。故障场景保存29个有效结果及3条技术失败，原生execution_status=partial_failed；共享任务存储status=failed是既有合同，成功010目标仍可比较为same。生成/合同调用预算未变。

主协调逐函数反查确认Worker与09bf参考完全相同；候选共享抽取器相对D提交基线只新增3个语句节点并替换13个异常返回，AST等价检查通过。移除本修复后，实际工作区共享抽取器与实施前文本精确相同，005/006既有内容完整保留。候选索引仅6个白名单文件，原两份他人暂存文档保持。最初忽略空白的候选patch造成两处缩进不等价，被候选编译门禁拦截、未提交；严格空白匹配的v2候选通过编译和上述验收，旧尝试留作过程证据。

另一名Sol6.1 medium只读独立审查未发现本次阻断缺陷，结论限定实际工作区diff，不冒充其审查过候选索引。其指出017的appropriateness=unknown运输分支测试不是实际原生输出证明，主协调亲自核对course_event_rules.py:248及semantic_extractor.py:729确认：模型枚举不含unknown，真实快照会转None。本次不据该构造单测宣称真实017未知事实保护；来源缺口reason仍不在转换白名单，合法semantic_state/item_states/文书unknown及002/008门控分别有保护。005/006专项grounding retry的既有异常处理未进入本闭环，不能宣称所有抽取异常已经统一技术交付。

过程证据：[工作区聚焦回归](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-shared-regression-private.json)、[候选索引176项](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-delivery-chain-candidate-v4-unit-private.json)、[候选API链](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-delivery-chain-candidate-v4-private.json)、[差分与原修改保护](C:/Users/Coldplay/.codex/worktrees/lx0916-validation-handoff/LX888/apps/medqc-web/.tmp/0910-full-audit/20261005-long-root-d-shared-diff-check-private.json)。无真实PG、QC模型或环境文件读取；认证仍为合成覆盖，页面未验证。此闭环关闭交付缺陷，不增加单规则临床验收完成数。
