# LX0609 引擎阶段 A：两试点源材料可用性与离线执行记录

代码时点：`f7bd7755698050a3b4bc62ee280aa45033344020`。本记录只证明当前本机源材料可读取、病理确定性执行可运行；不构成医学结论金标准，也不关闭 A0 保护集合验收。

## 范围与来源

- 规则：抢救 `LX0609-09-01-02`、病理报告完整性 `LX0609-06-02-01`。没有修改 0609 医学判据、Prompt、0916、CT 或并发配置。
- 从 `qc.manual_problem_sample_pools` 中名称为 `0910` 的 30 份样本定位住院三坐标，再按三坐标对 `cdm` 源表做限量只读查询。连接设置 `default_transaction_read_only=on`、`statement_timeout=5000`，每表每例最多接受 8 行；无数据库写入和真实模型调用。
- 30 份样本内，源表候选计数为：抢救记录 1、病理检查主表 10、病理报告 8。冻结 R01（一份抢救记录、一条抢救医嘱）、P01（一主表一报告）、P02（三主表一报告）、P03（三主表三报告）。私有坐标与原始源行仅保存在 `.tmp/0910-full-audit/phase-a-source-candidates-20260924-private.json`，不可提交。
- 查询投影包含源表中实际可用的 `document_id`、`is_deleted`、`record_status`。当前源表中仅 `rescue_record.document_id` 可用；所查病理两表没有这些列，病理业务键另存于私有快照。未按删除或状态字段筛行。这里保存的是 **CDM 候选源行**，不是生产 Evidence Session；不能凭局部查询未截断断言上游同步完整。抢救医嘱的名称和取消状态过滤也只用于材料探测，不代表生产全部门控。

## 离线执行结果

基于上述新冻结源行，以本次本地查询未截断为输入条件，调用当前 `evaluate_pathology_report_completeness`；无模型请求：

| 候选 | 主表/报告行数 | 当前程序输出 | 事件数 |
| --- | ---: | --- | ---: |
| P01 | 1/1 | `compliant / pathology_reports_complete` | 1 |
| P02 | 3/1 | `data_gap / pathology_report_completeness_unproven` | 3 |
| P03 | 3/3 | `compliant / pathology_reports_complete` | 3 |

可重复执行的私有脚本和完整事实产物分别为 `.tmp/0910-full-audit/phase-a-pathology-replay-private.py`、`.tmp/0910-full-audit/phase-a-pathology-replay-20260924-private.json`。脚本按源表全量行序给匿名引用稳定编号，避免不同病理事件引用碰撞；这些引用并非生产文书定位，不能据此验收生产证据链。命令 `python -X utf8 .tmp/0910-full-audit/phase-a-pathology-replay-private.py` 退出码 0。P02 的 `data_gap` 是当前程序输出，不能独立证明病历确有资料缺口。

## 尚未验证

- 抢救规则在存在可用记录时会请求一次 LLM 提取；本次没有冻结对应模型响应，因此没有对 R01 做结果回放，也没有增加模型调用和 Token。抢救规则的确定性早退分支不需要模型，但 R01 不属于该分支。
- 上述候选是新抽样，并非既有已验收保护病例。两试点尚需独立业务复核后的正负/资料不足基准、与对应代码及模型响应时点绑定的保护集合，才可做零回退断言。不能用当前程序自身输出给自身判定背书。
- 尚未将本次 CDM 源行经生产 `source_evidence_reader`、完整执行入口与 Finalizer/Store 回放；局部源查询的 `complete` 只表示本次没有达到行数上限，不能证明源系统没有其他记录。

## 主协调独立复核

主协调亲读取数与回放脚本，独立执行病理回放得到上述相同三例结果；P02 为两个 `pathology_execution_unproven` 事件及一个 `pathology_report_present` 事件。独立只读查询 `information_schema.columns` 确认所述追溯字段可用性。匿名引用已按源全量行编号，无跨事件重复。未把该结果升级为临床验收。
