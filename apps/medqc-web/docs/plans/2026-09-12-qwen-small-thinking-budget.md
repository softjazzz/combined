# Qwen 小预算思考对照：256 / 512 / 1024

## 问题证据、目标与待验证假设

用户明确要求降低思考开销并同意测试 256、512、1024 三档。上轮四例实测不设预算的思考平均耗时 38–50 秒，含推理输出合计约 2.2 万 token/模型，仍未全部通过事实/引用门槛。当前生产客户端已支持思考开关，但不接收或发送 thinking_budget。

阿里云[官方说明](https://help.aliyun.com/zh/model-studio/deep-thinking)及[错误码说明](https://help.aliyun.com/zh/model-studio/error-code)要求 thinking_budget 为正整数、不超过相应模型最大思维链长度。它限制推理过程，不等于 max_tokens；不以输出总 token 是否超过预算判断供应商违约。

待证伪假设：小预算能明显降低耗时，并保留足够的关键事实和关联判断。不能预先把 512 当最佳配置，不能因模型同意或响应成功就声称准确。

## 最小实施及文件范围

- `backend/app/services/qc_llm_client.py`：读取已有 custom_parameters 中可选 thinking_budget；默认 None。仅在现有阿里云 Qwen3 分支、enable_thinking=true 时发送。拒绝 bool、非整数、零和负数；模型相关上限由上游原错误路径处理，不硬编码一个适用于所有模型的最大值。
- `backend/app/services/llm_config_loader.py`：现有客户端重载配置时同步/清空 thinking_budget，避免沿用旧预算。无数据库写操作。
- 新测试 `backend/tests/unit/test_qc_llm_client_thinking_budget.py`：通过 generate 的真实 HTTP 请求边界验证三档、未设置、关闭思考、其他供应商、非法值及配置重载/清空。
- 不新增 UI、全局开关、配置表、规则层或重试。上述两个文件未达巨型文件门槛；这是已有参数组装/重载职责，无需独立模块。生产增量目标小于 30 行。

## 真实试验与验收

输入固定为 `exam-current-28f988f45-inputs-private.json` 中 C05/C06/C08/C12，沿正式 Bundle 主链捕获；仍以现有两个独立 gold 文件、主协调已复核的 9 个事件/18 条事实为门槛。C05 操作性事件不纳入真值，但保留在实际生产输入中。

Flash / 35B 各跑三档，每档四例，共 24 次真实请求，禁用长度重试和重复投票。普通模式参照上轮保存的同一输入回答（`exam-current-thinking-off-*-r1-private`），明确属于历史固定对照；若出现达到全部门槛的候选，才追加一次候选复验以检验稳定性。

校验实际 HTTP payload 的 budget、思考开关、模型及完整提示词；核对 usage 推理子字段（供应商不返回时标为不可直接验证）、耗时、输出是否完整、事实/引用正确性，并经当前生产链冻结回放。所有患者产物仅放 `.tmp/0910-full-audit/*-private`，不提交。

默认路径保护集合：提交 `8e3097789` 后 `n012-full30-qwen-control-default-after-private.json` 的全部 150 项。未设置预算的行为必须不变。编码/lint及相关客户端测试作为提交门槛，不因已有非本轮 BOM 问题改写他人文件。

未达到门槛不更改数据库/默认模型/默认预算，不将 011/012 标已解决。风险是预算过小造成推理不充分、输出遗漏或不同语义偏差；真实结果决定是否推荐，而不是只选最快一档。

## 实测收口

预算接入完成；主审退回初稿的非法值静默取消预算行为，改为请求阶段拒绝。64 项相关测试通过，默认 150 项完整结果不变。24 次真实调用的实际思考 token 均等于预算；三档两模型全部仅 1/4 病例达到完整门槛，不新增正式默认、不追加无依据的重复调用。

详见 [小预算验收记录](../acceptance/2026-09-12-qwen-small-thinking-budget.md)。
