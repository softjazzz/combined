# LX0609-08-01-02 出院带药审查问题修复

日期：2026-10-07。对应独立审查 D-MED-01 / D-MED-02，规则依据沿用062现有合同：药名、剂量、途径、用药时间或频次，不新增剂量医学正确性判据。

## 修改

仅修改 `native_extended_document_execution.py` 的出院带药信号及 `_structured_discharge_medications`。同文件其他代理负责术后/危急值片段，不在本记录修复范围。

- 明确注射、外用/外涂、吸入等给药方式、po/sc等缩写及数值用量进入现有受控抽取，不依靠药名词典。没有模型客户端时继续返回既有技术失败状态，不能将其当作无带药或已合规。
- 固定标签按药品名称划分条目，检查全部药品；单药标签乱序继续支持。多药前置字段或条目内重复字段归属不明时转受控抽取，禁止覆盖字段或跨药借用。
- 多份出院记录逐行收集固定标签/结构化药品，并绑定全部所选文书。任何一份相关记录未解析或结构化格式非法时保留资料缺口，不再让首份成功遮蔽后份。多个自由文本记录仍不会猜选一份调用模型。
- 普通休息、复诊、伤口换药护理和未来化疗评估不变。明确无带药沿用原抽取合同，不新增否定文本启发式。

本次是已复现给药写法与重复标签的有限修复。无任何给药信号的文本仍沿用已有不适用判断；没有证明任意药名、任意自由文本均可被可靠识别，不能把本次结果称为完整药物识别能力。

## 验证

先添加 `backend/tests/unit/test_discharge_medication_audit_regressions.py`，修复前12项为8失败、4通过；最初私有脚本三例全部复现。修复后专属回归扩至22项，全部通过。

执行以下相关回归共 **479通过**（15项既有依赖弃用警告）：

```powershell
python -m pytest backend/tests/unit/test_discharge_medication_audit_regressions.py backend/tests/unit/test_luxian_0609_discharge_medication_integration.py backend/tests/unit/test_luxian_0609_discharge_medication_extraction.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q --tb=short --disable-warnings
```

专属保护含：注射/外涂/po/sc、两药均完整、第二药缺途径时间、单药乱序、重复字段歧义、多份记录后药缺项、资料缺口不被首份遮蔽、所选两份文书证据绑定、通用随访/护理/未来化疗、明确无带药。经真实执行器→绑定归约→Canonical最终装配验证两药缺项仍为不合规、medication_count=2，注射等受控抽取一次调用及Token统计不变。抽取使用固定返回的测试替身，未调用真实模型。

私有复现脚本已改为正确行为断言并复跑通过：注射/外涂在无客户端时为technical_error/model_transport_error（不再not_applicable）；重复标签为non_compliant/requirement_violated，count=2，缺duration与route。私有脚本不提交。

`python -m ruff check` 对修改的生产文件与新增测试通过。新增源码及文档UTF-8无BOM、LF；未整文件格式化。

## 证据限制

全部新增反例为合成资料。未重新读取真实病例、未调真实模型、未创建PG任务或进行PG写入、未重启服务。验证覆盖正式原生执行器与最终Canonical装配，未跑发布→保存→API/浏览器端到端；不能称线上结果已更新、临床验收已通过或真实模型准确率提升。独立审查六例的历史一致结果不能替代当前版本临床验证。原审查文档保留为修复前基线。

## 交叉审补充：标签值前导换行

交叉审发现新解析器先按换行分割会把冒号后换行的合法值截为空。新增 `test_label_value_on_next_line_remains_complete`，修复前实际为non_compliant，单项红灯确认。最小修复在分割前对值片段 `lstrip()`，恢复原标签正则对前导空白的兼容，不跨越药品边界。

补修后专属 **23项通过**，生产文件与专属测试Ruff通过；本次未重复运行479项宽回归，其通过记录对应补修前版本。
