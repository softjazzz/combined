# 011/012：修复 Qwen 显式思考配置并验证实际效果

## 证据和待证伪假设

主协调已重跑 `check-fixed-exam-evidence-private.py --assert-correct`：两例五个已核对影像事件，普通模式 8 份回答均有事实或引用错误。旧思考对照为 7/8，不能据此宣称所有病例已解决。本轮另由独立代理复核旧真值及两个新增病例，不能把模型一致当作准确。

代码调用链为配置中的 `custom_parameters.enable_thinking` → `SichuanQCLLMClient.enable_thinking` → `generate` 的 `_build_provider_specific_payload` → HTTP payload。主协调构造 Qwen3.6 客户端明确开启思考，断言请求值为 true 已失败，实际发送 false。该分支仅尊重 DeepSeek 的思考设置。

根因假设（已用上述调用链及失败断言验证配置路径，业务效果仍待验证）：Qwen 对照无法通过现有配置启用思考，妨碍对模型错误开展可复现的受控比较。不能将 011/012 所有误判归因于这个配置缺陷。

阿里云[官方思考模式说明](https://help.aliyun.com/en/model-studio/deep-thinking)说明支持的 Qwen 混合思考模型可按请求设置 `enable_thinking`，并用 `thinking_budget` 控制推理长度。此次生产修改只落实已有开关，不新增预算或全局配置；思考预算若用于试验必须单独标注。

## 最小方案、文件范围和失败语义

- 仅修改 `backend/app/services/qc_llm_client.py` 与独立测试 `backend/tests/unit/test_qc_llm_client_qwen_thinking.py`。
- 对阿里云 Qwen3 系列请求尊重已有显式思考设置；默认关闭保持不变。识别现有 provider_code 或官方 DashScope host，保留 DeepSeek 优先分支；不向其他供应商/非 Qwen3 模型推广参数行为。
- 不修改规则、解析器、Bundle、状态映射、数据库配置、默认模型或任何全局开关。上游参数/模型不支持时仍按原错误路径返回，不能假装思考已生效。
- 现有客户端负责供应商参数，这是原有职责中的缺陷；无需新增模块、注册表或第二个事实所有者。预计生产代码增量不超过 12 行。

## 验收

1. 先红后绿：测试必须通过 `generate` 的 HTTP 请求边界检查 Qwen 开启/关闭/默认、provider/endpoint 识别，以及其他供应商、DeepSeek 不回退；不能只测局部布尔函数。
2. 当前提交 `28f988f45` 下保存 `exam-current-28f988f45-inputs-private.json`，源自正式 Bundle 只读主链。固定这些输入，对 Flash、35B 的普通/思考模式作对照，核对真实请求参数、供应商响应、调用数、token、耗时及逐事件结果，不凭请求值证明模型实际思考。
3. 保护集合为 `n012-full30-culture015-full-after-private.json`（015 修复后时点）的全部 30×5 项；默认参数路径改前改后完整结果应相等。模型模式对照属于新回答，差异必须逐事件复核，不能套用旧回答零差异作为正确性证明。
4. 未达到逐事件真值门槛，不全局切换模型或开启思考，不关闭原 011/012 台账。即使开关修复完成，语义错误仍单列。

## 剩余风险

思考显著增加 token 和耗时，且既有 Flash 试验仍有漏认。两例真值可能受关联解释影响，须先独立核对。此次允许完成一个配置缺陷和有边界的模型对照，不混入影像关键词平台或不受控重试投票。

## 验收结果

配置缺陷已修复，生产增量 9 行，40 项相关测试通过。四例当前输入完成 16 次真实请求，均通过精确提示词验证进入生产归约；默认路径 150 项完整结果不变。思考模式两模型均仅 2/4 病例通过当前门槛，未达到全局切换条件，011/012 不标完成。

主协调推翻了“C06 多引用导致时间缺失”的初步猜测：原投影实际缺评价截止时间。完整证据、成本和未解决问题见 [验收记录](../acceptance/2026-09-12-exam012-thinking-control-comparison.md)。
