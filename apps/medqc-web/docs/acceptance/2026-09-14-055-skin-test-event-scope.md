# LX0609-055 皮试事件范围修复验收

## 结论

055 已不再把 `drug_apply_method=皮试` 的抗菌药医嘱当作治疗起点或 48—72 小时评价事件。修复限定在 055 的事件资格边界，054、057、058 的医嘱输入保持原行为；未增加 LLM 调用、状态、Schema 或第二条事实链。

本次关闭的是“皮试进入 055 治疗窗口”这一确定性缺陷。C01、C02、C14 仍不关闭：去掉皮试后还需按首次实际给药时间核验剩余阿莫西林或哌拉西林事件及评价关联。当前代码用计划开始时间或医嘱下达时间代理实际执行时间，该问题属于后续独立闭环。

## 修复与代码边界

- `native_extended_document_execution.py::_055_treatment_orders` 在 055 建窗前排除明确标为“皮试”的医嘱。
- 055 的空触发判断和 `order_events` 使用过滤后的集合；其它抗菌药规则继续使用 `_antimicrobial_orders` 的原集合。
- Renderer、Finalizer、Aggregator 不参与修正，客户状态和证据仍来自规则执行器。
- 只处理真实样本已出现的精确字段值“皮试”，没有推断“试敏”等未验证同义值。

## 真实病例重放

使用 `medqc_sample_0910_typed_20260910` 的正式 Evidence Session / Bundle 只读重放，数据库写入 0、LLM 调用 0、Token 0。私有产物 `.tmp/0910-full-audit/055-skin-fix-20260914/055-skin-fix-before-after-private.json` 对同一 Evidence Session 分别加载 `git show 616f6e732:.../native_extended_document_execution.py` 的修复前模块和当前工作树模块，再经过 binding、reducer、finalizer，形成可复算的前后对照。修复后主审完整回放另存于同目录 `root/antibiotics-current-replay-private.json`。

| 病例 | 修复前 055 事件 | 修复后 055 事件 | 修复后终态 |
| --- | --- | --- | --- |
| C01 | 青霉素、阿莫西林、阿莫西林 | 阿莫西林、阿莫西林 | `data_gap / association_failed` |
| C02 | 哌拉西林、青霉素、哌拉西林 | 哌拉西林、哌拉西林 | `non_compliant / threshold_exceeded` |
| C14 | 青霉素、阿莫西林、阿莫西林 | 阿莫西林、阿莫西林 | `data_gap / association_failed` |

三例的 055 事实引用数和客户证据数均从 3 降为 2，来源仍为 `inpat_drug_order`。这证明皮试医嘱本身及对应事件已从实际输出移除；终态未被人为改写。C01、C14 仍因同名治疗医嘱关联不唯一而资料不足，C02 在当前代理时间下仍超过阈值。

## 测试

- 新增混合事件回归：皮试与静滴治疗同时存在、静滴后 48 小时有评价时，只保留静滴事件并合规。
- 新增纯皮试回归：只有皮试医嘱时，055 为 `not_applicable / trigger_absent_complete`，不生成 055 展示事件。
- 纯皮试负向结论仍绑定 `inpat_drug_order` 的来源完整性快照哈希，用于证明来源已经完整检查；它不是皮试行的逐文书引用，也不会投影为客户证据。
- `test_luxian_0609_native_extended_document_execution.py`：408 项通过。
- 其中 055 聚焦测试：23 项通过。
- `test_luxian_0609_antimicrobial_result_mapping.py`：49 项通过。

保护集合继续以提交 `616f6e732` 的已关闭及聚焦通过记录为基准。真实病例重放只证明皮试范围修复生效；计划时间与实际给药时间的合同冲突、剩余治疗关联和全 30 例正式任务回归仍需后续验收。
