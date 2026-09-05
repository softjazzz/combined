# 会诊 020–023 合成真实模型性能复放

## 范围

本材料只覆盖 `LX0609-020` 至 `LX0609-023` 的原生会诊主链：

```text
合成会诊资料 → native consultation episode 执行器 → RuleDecision reducer
→ aggregate_luxian_0609_results → Canonical 客户结果
```

输入固定为 `backend/tests/fixtures/luxian_0609/consultation-family-replay.json` 中的合成会诊、
病程和住院边界资料。真实模型仅接收这些合成资料；脚本不读取业务数据库或真实病历。
真实模型客户端复用已有 `NullLLMCallEventStore`，因此基准也不会写入 LLM 观测表。

2026-09-05 修正：原夹具会诊意见同时写有“复查血常规”和“继续保肝治疗”两条明确建议，但
后续合成病程仅记录前者执行，受控响应却只抽取一条建议。真实模型据原文正确识别两条建议，
因而触发复核并将 023 判为不合规。为使本基准固定验证“单条明确建议已被执行”的目标口径，
夹具正文已收敛为“建议复查血常规。”；严格的全合规、两次调用门槛保持不变。

离线合同复放仍由 `backend/scripts/verify_consultation_family_acceptance.py` 完成，使用夹具内受控
响应且保持零网络。它与真实模型性能采样是两个独立入口，后者不会由前者隐式触发。

## 手动运行真实模型基准

真实模型调用不进入 CI，且必须显式确认：

```powershell
Set-Location D:\LLM\LX888\apps\medqc-web\backend
py -3.10 .\scripts\run_luxian_0609_consultation_synthetic_benchmark10.py `
  --fixture .\tests\fixtures\luxian_0609\consultation-family-replay.json `
  --real-model
```

固定执行 1 次预热和 10 次正式轮次。每轮只输出：

- 逻辑 LLM 调用数、输入/输出/总 token、执行器累计 API 耗时和端到端耗时；
- 020–023 的 `status` 与 `reason_code`；
- 与预热轮次的内存 Prompt 逐字一致性和各 Prompt 长度；
- 执行器 usage 与每次模型返回 usage 的守恒比较（字段名为 `usage_conservation`，不是
  正式 FamilyUsageAttribution）；
- 由同一合成调用序列推断的重复 Prompt / 复核提示，以及直接原生链结构属性
  `legacy_path=not_invoked_direct_native_chain`；
- 非敏感的 provider、model、`temperature=0`、top-p 与 max tokens，确保可复放。

Prompt 只在当前 Python 进程内比较，不写入输出、文件或摘要。当前公共执行合同没有暴露每次
逻辑调用内部的 HTTP attempt 计数，因此该字段会明确输出为
`unavailable_without_public_execution_trace`；`network_observation=unknown` 也不会把“允许真实
模型联网”误报为“已经观测到网络请求”。预热轮若任一质量门失败，会输出受控 `failure_kind` 并
直接中止，不继续消耗十轮正式调用。

`benchmark_passed=true` 的固定门槛是：预热和 10 次正式轮次均完成；每轮恰有 020–023 四条规则；
四条均为 `compliant / requirement_satisfied`；无 `technical_error`；逻辑调用与委托调用均为 2；
Prompt 与预热逐字一致；usage 守恒。脚本按此字段返回 0/1，不能因“完成了十轮”而误报通过。

## 当前证据状态

- 单测已用受控客户端验证：1 次预热 + 10 次正式轮次、Prompt 一致性、usage 守恒、020–023
  状态/原因码、以及 HTTP attempt 的不可用标记。
- 2026-09-05 已按上述命令实际完成 1 次预热和 10 次正式轮次，进程退出码为 0，
  `benchmark_passed=true`。模型为 `qwen3.7-flash`，provider 为 `alibaba`，
  `temperature=0`、`top_p=0.9`、`max_tokens=16384`、超时 120 秒。
- 10/10 正式轮次均为 020–023 四条规则 `compliant / requirement_satisfied`；每轮恰好 2 次
  逻辑模型调用，输入 1015 tokens、输出 190 tokens、合计 1205 tokens；Prompt 与预热逐字
  一致，执行器与模型响应的 usage 全部守恒，没有 `technical_error`。
- 本轮 API 累计耗时中位数为 1802.843 ms，端到端耗时中位数为 1864.421 ms。逐轮原始值如下，
  不含预热轮：

| 轮次 | API 耗时（ms） | 端到端耗时（ms） |
| ---: | -------------: | ---------------: |
|    1 |       1601.631 |         1662.531 |
|    2 |       1953.008 |         2021.247 |
|    3 |       1672.631 |         1738.185 |
|    4 |       1985.534 |         2030.851 |
|    5 |       1637.705 |         1700.745 |
|    6 |       1650.791 |         1711.293 |
|    7 |       2402.372 |         2463.637 |
|    8 |       2420.510 |         2486.764 |
|    9 |       1860.369 |         1922.547 |
|   10 |       1745.317 |         1806.296 |

这组数据建立了修正后单建议夹具的可复放当前基线。由于旧 B3 性能表使用的是不同范围和旧夹具，
不能据此宣称完成同输入的跨版本 10% 性能比较；后续版本应直接复用本脚本和本夹具进行同协议对比。
