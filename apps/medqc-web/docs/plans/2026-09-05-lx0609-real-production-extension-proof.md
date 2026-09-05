# LX0609 真实生产规则扩展成本验证

## 目标

用两条已有业务定义、但尚未进入 LX0609 正式目录的规则验证生产扩展边界：

- `LX0609-076`：死亡记录中的死亡时间是否完整，来源规则 `LXE-43`；
- `LX0609-077`：首次病程鉴别诊断是否围绕第一诊断展开，来源规则 `LX-011`。

两条规则必须进入正式 master、phase、wrapper、contract、Native Package、统一执行引擎、Binding、公共证据投影和 Canonical Result，不使用测试专用规则号，不进入旧兼容执行器。

## 规则口径

### LX0609-076

- 适用前提：本次住院已确认死亡且存在死亡记录；死亡病例无死亡记录仍由 `LX0609-060` 负责，076 不重复报错。
- 权威字段：死亡记录自身的 `death_datetime` 或 `death_time`。
- 正文回退：仅接受死亡记录正文中带有“死亡时间”字段，或“于……宣告临床死亡”这种高特异性表达；不得使用 `record_time`、`submit_time` 替代死亡时间。
- 结果：字段存在且可解析为 `compliant`；存在死亡记录但死亡时间缺失为 `non_compliant`；非死亡病例或死亡病例无死亡记录为 `not_applicable`；来源不可用、截断或权威时间冲突为 `data_gap`。
- 执行：`extended_document`，纯 Python，LLM 调用上限 0。

### LX0609-077

- 适用前提：存在首次病程记录，并能取得第一诊断和鉴别诊断正文。
- 输入：仅投影第一诊断、鉴别诊断条目和必要的首次病程短片段，不发送整份病历。
- 输出枚举：`related`、`unrelated`、`unknown`。
- 状态：`related` 为 `compliant`，`unrelated` 为 `non_compliant`，`unknown` 为 `uncertain`；缺少首次病程、第一诊断或鉴别诊断为 `data_gap`；模型超时、异常或结构非法为 `technical_error`。
- 执行：`course_quality`，每规则最多一次受控 LLM 调用。

## 修改边界

允许修改：

- 规则 master、phase、wrapper、contract；
- 规则族声明；
- 所属执行器的最小接线；
- 新规则独立深模块；
- 声明式客户文案；
- 聚焦测试、正式入口验收和本验收记录。

禁止修改：

- `luxian_0609_result_aggregator.py` 的规则专属分支；
- 公共任务编排入口；
- 保存逻辑、API DTO、前端状态解释；
- 旧兼容执行器、fallback、第二套状态机或第二套证据投影。

## 五种覆盖形状

每条规则至少覆盖：合规、确定问题、不适用或资料缺失、边界/冲突、技术失败。077 另验证模型结构非法不会降级为 `data_gap` 或 `uncertain`。

## 验收

1. 正式目录为连续的 `LX0609-001` 至 `LX0609-077`。
2. 076 的 `executor_key=extended_document`、LLM 调用数为 0。
3. 077 的 `executor_key=course_quality`、单次执行最多 1 次 LLM。
4. 单规则、批量质控、客户样本验证使用同一 Native 执行链，Canonical 结果一致。
5. `fact_refs` 经 Binding 验证，并由公共投影得到真实文书 ID、字段和记录时间。
6. 聚合器、保存、API DTO、前端解释文件相对实施前零改动。
7. 记录实际新增/修改生产文件、生产代码净增量、测试文件和执行耗时，作为真实扩展成本。
