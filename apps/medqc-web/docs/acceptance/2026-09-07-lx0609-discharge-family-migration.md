# LX0609 出院文书族结构迁移验收

## 范围

本次只迁移 `LX0609-061/062/063/067/068` 的客户展示事实合同与证据所有权，
不修改原生判定、状态口径、Prompt、API、保存链或前端。

## 职责收口

- `discharge_result_mapping.py` 是五条规则客户展示事实与状态自洽的唯一合同所有者；
  它只白名单化执行器已裁决事实，不读取文书材料，也不生成客户证据。
- Finalizer 接管五条规则的合同失败收敛，并保留技术失败为 `technical_error`。
- 客户文书证据只沿 `fact_refs → Binding → 公共 selected-document projector` 投影。
  对 067/068 无精确逐行坐标的情况，保持无客户证据，不回退为来源级或私有文书
  ID 搜索。
- Aggregator 已不再出现这五条规则号或其专属事实/证据分支；测试设有文本归零守卫。

## 冻结行为

- 061 保持既有 `inpat_registration.discharge_datetime` 权威时间回退。
- 067 保持 `course_present=False → data_gap/source_empty` 的现行口径。
- 068 保持活跃执行链：`daily_course_record + automatic_discharge` 与
  `senior_course_record + senior_approval` 均可形成合规结果；旧 Aggregator 中位于
  通用分支之后、不可达的 senior-only 分支未作为合同基线。

## 验证

- Mapping、Finalizer、Aggregator 完整单元回归：442 passed。
- 出院族原生执行聚焦（061/062/063/067/068）：33 passed。
- 含危急值跨族 canonical 投影的聚焦回归：21 passed。
- Aggregator 五条规则号引用：0。
- `git diff --check`：通过。

全量原生扩展文书测试曾同时观察到 065 的窗口相关失败；该失败来自并行任务修改，
不属于本次出院族变更，故未在本提交中调整。
