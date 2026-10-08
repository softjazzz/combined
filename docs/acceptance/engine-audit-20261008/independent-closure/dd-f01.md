# DD-F01 固定提交独立复核

固定源提交：`58e29ffe9edc559bee552c734dc66ebed9ebf32c`，工作树 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`。开始时树干净；提交仅8批准路径，每文件SHA256保留在 `independent-fixed-58e29-source-manifest.json`。

**39/39独立检查通过，DD-F01在本次冻结工程边界内关闭。** 开发侧73+8绿测没有计入独立结果；未扩跑全套。独立检查使用原DD-S01及审计者预先冻结的八项JSON，不读取开发测试中的预期数组，不改变原死亡同名合规预期。

| 范围 | 数量 | 结果 |
|---|---:|---|
| 原DD-S01结果与死亡文案、精确death引用、无ID mr来源锚点、无虚假出院父文书 | 5 | 5/5 |
| 八项typed死亡独立冻结 | 8 | 8/8 |
| 可读死亡正文的真实death文书坐标 | 1 | 1/1 |
| 普通出院旧facts全等与death/登记来源不可用三组合 | 4 | 4/4 |
| 两类scope gap合法facts全等、每类8个公开非法status拒绝、仅data_gap接受 | 20 | 20/20 |
| 063内部决策支持来源精确集合 | 1 | 1/1 |

权威mr死亡类型在无death_record、登记未知时支持死亡内容核对；明确存活/在院矛盾与无上下文混合终末类型返回data_gap；已确认死亡时刻冲突不掩盖确定内容冲突。普通出院结果没有新增scope字段，旧公开facts全等。新增公开scope gap严格拒绝空、unknown、technical_error、uncertain、not_executed、compliant、non_compliant、not_applicable状态。

独立探针及结果：`independent-fixed-58e29-probe.py`、`independent-fixed-58e29-results.json`；检查计划在生产执行前保存为 `independent-fixed-58e29-check-plan.json`。运行6.5秒，退出0；真实模型、PG连接、网络与.env读取均0，所有输入为合成。探针沿现有合成Evidence Session辅助构造，再调用执行器/绑定/归约/公共聚合与公开Finalizer，不执行开发专属测试文件。

八冻结SHA256：`ba15b3e8b125c725a8ac8c973959ef2ad9d121a6fb36d06020c39e69177656f4`。

独立结果SHA256：`2ce1c41cd2ad0276ff25f66172c6b2b5dc7d99488e754276bec35beb087c65fc`。

工程关闭不等于客户临床验收；未核验真实患者死亡文书物理来源或临床诊断选择，未关闭062的药名/剂量一致性覆盖限制及027口径文档对齐项。0916仍排除。测试槽运行后立即释放，没有继续新增测试。
