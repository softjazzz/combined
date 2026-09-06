# LX0609 手术文书族职责收口验收记录

## 范围

本次仅迁移 `LX0609-029/034/035/036/037/038/039`：术前小结、麻醉知情同意、麻醉访视、麻醉记录和术前讨论。

- 执行器：实际判定及精确 `fact_refs`；
- `surgery_document_result_mapping.py`：客户展示事实合同和旧 aggregate 直调的最小兼容；
- Finalizer：合同/状态一致性校验，非法输出 fail-closed 为 `technical_error`；
- 公共 Binding / selected-document 投影：从 `fact_refs` 投影真实文书坐标；
- Aggregator：仅装配结果。

未改动 Prompt、LLM 调用、Token、Renderer 文案、API、数据库、任务入口或来源注册。

## 允许的证据坐标修正

本次不改变冻结用例的 `status`、`reason_code`、客户展示事实、findings、LLM 调用数或 Token。原聚合器使用来源级观察事实、或将裸 `source_document_id` 映射到错误文书类型；现改为执行器选择真实 `fact_refs`，再由公共投影生成证据。

因此，客户证据坐标会从来源级/错误坐标收敛为实际文书坐标。这是批准的“证据单一所有者”修正，不属于质控口径变化。验收按 `(source_type, source_document_id)` 的集合比较，数组顺序不表示优先级。

## 旧入口最小兼容

- `034/036` 仅把现有裸 `source_document_id` 映射为 `anesthesia_record`；
- `039` 仅接受 `surgery_record` 或 `mr_surgery`；
- `029/035/037` 不从裸字段猜测文书；
- `038` 不投影裸 ID。

## 归零守卫

冻结测试读取聚合器源码，断言该文件不再包含本族七条规则号。实际运行时由 Finalizer 统一接收受控事实；无效合同或状态冲突只形成 `technical_error`，不伪装为资料不足、待确认或临床缺陷。
