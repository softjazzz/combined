# LX0609 `/test-rule` 旧判定链退役验收

## 问题与根因

`POST /api/v1/qc/sichuan/test-rule` 的请求合同只有 `rule_id` 与 `medical_text`。
它不携带正式 LX0609 链所需的就诊三坐标、结构化事件、来源材料或关联关系，不能安全
调用 native → Binding → Canonical 的正式链。

此前路由在此纯文本输入上：

- 用 `_apply_luxian_time_rule` 重算 `001/002/003/004`；
- 用 `_apply_luxian_preop_surgeon_rule` 重算 `039`；
- 再以 `_normalize_luxian_single_test_result` 的文案正则覆写其余 LX0609 的状态。

这会让路由成为第二个临床判定所有者，并可能在本应拒绝的输入上落入通用 LLM。

## 调用者与边界

前端调用点是规则管理和演示页面的“测试规则”对话框：
`src/api/qc.ts`、`SemanticRulesManager.vue`、`BatchEvaluationModal.vue` 与
`workstation-v4/semantic-rules/service.ts`。它们均只提交纯文本。客户样本验证和正式单
规则执行使用 workspace 入口，携带就诊/结构化资料，未改动。

## 修改与行为

当 `_load_single_test_rule()` 识别到 LX0609 包装规则时，路由立即返回 HTTP 422：

> LX0609 规则必须通过客户样本验证或正式单规则入口执行；纯文本测试无法提供所需的
> 结构化事件和关联字段。

拒绝发生在 `rule_engine.evaluate()` 之前，因此不回退通用 LLM。普通 SC 规则保留原有
`rule_engine.evaluate()` 和响应字段映射。

已删除仅供该旧路径的日期解析、标签抽取、时限重算、术前术者重算、局部调度和文案
正则状态覆写函数；路由也不再包含 `luxian_time_rule` 或
`luxian_preop_surgeon_rule`。

未修改正式执行引擎、规则口径、Prompt、Store、Aggregator 或前端。

## 验证

`test_qc_sichuan_test_rule.py` 覆盖：

- 经认证 API 请求 `LX0609-001/003/004/039` 均为 422；
- 每次拒绝均断言 `rule_engine.evaluate()` 零调用；
- 普通 `SC-001` 仍调用原引擎，并保留原请求 DTO 与 token 映射；
- 源码守卫禁止全部七个旧函数和两个旧本地 engine 标记回流。

实测：该路由测试 **6/6** 通过；变更路由及测试 Ruff 通过；目标文件 diff check 通过。

## 剩余风险

现有纯文本“测试规则”界面对 LX0609 会显示受控 422，不再提供模拟判定结果。若要提供
LX0609 试运行体验，必须另立任务并接入已有客户样本验证或正式单规则入口，不能恢复
纯文本 fallback。
