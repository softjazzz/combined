# LX0609 B-01～B-05及剩余发现：最小工程修复，待Claude复审

## 固定范围

- 开发基线：`94745e3b682a05b87335acf7d9196c0b8dcc2d35`，分支 `codex/frozen-exam-association-fix-20261107`。本报告与修复同提交，最终提交号以 `git rev-parse HEAD` 和提交后隔离回执核对。
- 保留该基线已包含的C18、检查归属v6及四项公共修复；本次补充清单没有覆盖或替代B-01～B-05。
- 无迁移、配置启用、前端、集成分支修改。未推送、合并、部署、连接业务/CDM/PG/模型/代理，不涉及0916或27份重跑。

## 问题与落点

| 项目 | 工程状态 | 最小修改与保留边界 |
|---|---|---|
| B-01 054/057/058、071、075时窗 | 已修复 | Provider与来源计划都接入统一终点；未成熟窗口不报缺陷；缺失或日期级精度不伪造时刻。沿用原24小时/3自然日等阈值。交接班只有能独立确认的缺陷优先。 |
| B-02 054/057/058、075正文与074候选上限 | 已修复 | 去掉局部正文裁切，仍受原总输入容量约束；不能完整核验则保留未决。074前三候选之外仍有材料时，局部否定不能确认该诊断缺理由；已定位正面证据仍有效。 |
| B-03 死亡来源、病原时间、出院日期 | 已修复/口径待确认 | 死亡来源错误不再借其他材料确认正常结果；病原学缺采样时间保留缺口，申请与采样跨用药时刻保留冲突；出院日期精度进入快照与引用身份，24小时规则不按午夜推断。 |
| B-04 无效医嘱 | 已修复 | 057/058使用既有实际给药过滤结果，明确取消/未执行不新增义务；已确认实施不会被取消标签再次丢掉。054保留独立口径与缓存；会诊候选排除明确作废/取消/撤销，不把停止当取消。 |
| B-05 危急值、会诊 | 已修复 | 确认超时优先于另一未成熟事件；会诊未知不再变合规或不适用；意见措施补核不能把未知事件重新覆盖成合规。独立确认缺陷仍保留。 |
| 补充05-01-01（并入B-02） | 已修复 | 感染证据正文完整发送且沿用原候选总容量，超过范围/候选时间不全不作完整否定。正面证据仅用于自身时间窗；有正面与未知文书时不抹掉未知。预算拒绝是技术失败且不丢同族成功，取消不吞掉。 |
| 补充01-01-02 | 已修复 | 程序确认长度FAILED优先，合法语义unknown仍作为unknown子项；不改长度算法。Binding可交付长度缺陷。 |
| 补充02-01-05（并入B-05） | 已修复 | 缺时间/关联失败逐事件收集，不提前返回抹掉已确认缺陷；新增可选`unresolved_events`受控事实经原映射、Finalizer、Canonical保存重读；不改变病危自然日合同。 |
| 补充06-02-03 | 已修复安全边界/口径待确认 | 使用同一冻结终点，晚于终点不报当前窗口缺失；等于终点没有被一律排除。明确终末闭合范围且完整未记录保留原否定；缺失/冲突/日期精度保留原因；运行中没有既定到期依据，不发明回报后X小时。有效记录仍可证明已记。 |
| 补充04-02-02 | 已修复安全边界/口径待确认 | Gate不再单以计划医嘱证明术后义务；未来计划、执行未知、明确取消、停止、可靠实施及取消/实施冲突分别处理。保留已实施缺记录的合法否定，不按文本猜执行。共用医嘱分类器仍表达计划事实，029术前小结不套术后豁免。 |
| 补充06-03-02 | 正式入口复现后修复 | 合成本地读取完整＋出院＋无报告原来输出确定不合规；现在保留`data_gap/target_report_missing`。读取完整不证明源系统确认未出报告。已存在有效报告及在院待回报的原路径保留，不新增培养时限。 |

主要生产修改：`native_extended_document_execution.py`、`extended_document/*`、危急值映射、`native_consultation_episode_execution.py`、`evaluation_horizon.py`、`evidence_snapshot_provider.py`、`source_registry.py`，以及补充清单列出的各原生执行器。没有另建执行器或改保存层医学判断。

## 冻结与历史

- 理由/特殊级会诊完整正文使用新的`order_reason_full_text_v2`、`special_approval_full_text_v2`命名空间；旧文件不删除、不覆盖。
- 感染证据Prompt协议v2；其抽取函数没有新增独立持久缓存。病程语义评价v4、病理评价v2及手术存在性评价v3标明新执行语义。
- 日期级出院快照新增精度，派生终点引用区分日期与精确午夜，旧任务快照不重写；仍沿用已有快照优先、旧入口兼容及模型身份隔离。
- 固定保护验证旧理由冻结未被读取/改写、预算失败不产生成功冻结、精度变化使身份不同。未对现场全部冻结文件做扫描或历史重算。

## 定向验证及命令

在`apps/medqc-web/backend`，Python3.10使用已有禁网入口，主动阻断真实网络与非SQLite数据库；不使用Claude自制驱动的退出码作为验收。

```powershell
$py = 'C:/Users/Coldplay/AppData/Local/Programs/Python/Python310/python.exe'
& $py -B scripts/run_pr8_offline_tests.py tests/unit/test_engine_blocking_findings.py tests/unit/test_engine_remaining_findings.py tests/unit/test_luxian_0609_frozen_discharge_horizon.py
& $py -B scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_course_quality_execution.py -k '018 or 009'
& $py -B scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_execution.py tests/unit/test_luxian_0609_deterministic_gate.py tests/unit/test_luxian_0609_handbook_exam_lab.py tests/unit/test_luxian_0609_prophylactic_antimicrobial_duration.py -k '030 or culture or surgery or 028'
& $py -B scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_tumor_pathology_execution.py -k '013 or 019'
& $py -B scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_extended_document_execution.py -k 'test_054 or test_056 or test_057 or test_058 or test_061 or test_071 or test_074 or test_075 or controlled_antimicrobial'
```

提交前已核对直接受影响的集合；提交后在同一HEAD执行以上必要终验，详细结果另附本机终验回执。不是全量质量门，也不是模型质量验证。开发中出现的反例、断言及原因码不匹配均实际修正后再验证，不把初次红灯隐去。

- 新增B保护38项，新增剩余保护30项。病理、病危混合事件、死亡来源以及预算失败同族成功分别涉及内存Canonical保存；病理与病危断言状态、原因、事实及证据集合重读一致。并非每一条规则都重新走数据库。
- 只读Store整理不算保存验收；本次使用`CanonicalResultStore.replace_for_job`提交到一次性内存SQLite后读取。
- 原未记录负向、完整正向、语义unknown、未来计划、取消、停止、已实施、时间精度、预算拒绝、取消及来源隔离做直接受影响对照；旧测试仅补必要的已闭合时间上下文，或将旧不安全断言更新为本次明确合同。
- 生产改动及新增保护文件的Ruff F、UTF-8/LF与`git diff --check`定向检查；不跑全库lint/build。

## 尚未验收/不能扩大结论

1. 病理在院回报到记录的期限、出院后补记义务尚需临床确认。超出本轮终点现在保守未决，不宣称医院未记录或病理规则质量已验收。
2. 手术计划/停止的现场状态语义、实施证据与多台次关联仍按既有可靠结构化合同；未扩展自由文本触发，未解决所有多台次记录问题。
3. 培养源系统确认漏报告与同步/关联缺口尚无权威区分凭据。不能仅靠本地缺行恢复确定否定。
4. 054未执行范围、停嘱口径、日期级出院时限及申请/采样跨边界选择等待确认；本轮不修改07-02-01已授权的输血触发。
5. 不顺带处理N-02～N-11及其他P3；C18历史运行代码、C27真实归属与06-01-04不完整回退主抽取等原有限制仍保留。
6. 未执行真实模型、PG16、现场数据、临床标注或医学质量验收。工程保护通过不能称为所有规则或模型质量等价。

结论：上述确定缺陷和安全边界完成本机工程修复，供Claude独立复审；临床口径未决项没有被写成新规则。不能据此自动合并、部署或批准正式医学交付。
