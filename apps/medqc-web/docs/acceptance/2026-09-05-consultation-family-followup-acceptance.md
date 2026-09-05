# 会诊族后续离线复放验收

## 范围与边界

`backend/tests/fixtures/luxian_0609/consultation-family-replay.json` 是脱敏的合成资料，
`historical_b3_response=false`。它不是 B3 真实病例、真实 Prompt 或历史模型响应，
只用于验证同类会诊执行合同的离线可复放性。

原 B3 的 raw response、逐字 Prompt 和逐轮材料均未留存。因此
`technical_error → compliant` 的历史首次分叉当前不可追溯，也不能以合成响应补造后
宣称复现。当前夹具只冻结正常合同。

复放脚本只接受夹具中的 phase1、phase2 受控响应，使用正式
`会诊执行器 → RuleDecision reducer → aggregate_luxian_0609_results` 链路。它不读取
数据库、不调用真实模型或网络，也不读取 `.env`。为兼容旧聚合器的客户安全投影键，
脚本仅在进程内提供一个固定合成 `JWT_SECRET`，不会输出该值或使用真实凭证。

## 运行

在 `apps/medqc-web` 执行：

```powershell
python backend/scripts/verify_consultation_family_acceptance.py `
  --fixture backend/tests/fixtures/luxian_0609/consultation-family-replay.json `
  --variant-root D:/LLM/LX888/.worktrees/b3-baseline-b98e26e72/apps/medqc-web `
  --variant-root D:/LLM/LX888/apps/medqc-web
```

输出只包含每条规则的 `status`、`reason_code`、客户 facts、事实引用数量和已解析的
文书坐标（来源类型、文书 ID、字段路径、记录时间）；不序列化具体 fact ref、摘要或
Prompt。双工作树都成功复放时，输出还报告
`prompts_byte_equal`、每个变体的 Prompt 数和 LLM 调用数，以及按规则比较的状态、
原因码、facts、证据坐标集合、事实引用数量和验收投影精确相等性。证据坐标按集合比较，
不会因输出顺序不同误报不一致。

跨工作树时，父进程为本次复放创建临时会话 HMAC key，仅通过最小子进程环境传入。子进程只
回传 HMAC marker，父进程据此精确比较 Prompt 字节；marker 不进入业务 DTO、普通日志或最终
公开 JSON。单进程复放仍直接在内存中逐字比较 Prompt，且不依赖任何外部环境变量。

本夹具在 b98 与当前工作区均会执行两次受控调用，且 Prompt 字节一致。当前的正常闭环
样本四条规则均为 `compliant / requirement_satisfied`。当前 b98 与工作区的业务状态、
原因码、facts 和证据坐标集合一致；但事实引用数量因单一所有者迁移而变化，因此包含
内部引用数量统计的验收投影不完全相同，不能声称内部行为完全等价；客户可见业务事实
和证据坐标仍保持一致。它尚未形成 B3 旧真实响应的
`technical_error → compliant` 首次分叉证据；不得把该正常合成样本描述为该历史分叉的
复现。

## Benchmark 协议

离线复放入口不再承载 benchmark 模式，避免其从零网络合同隐式转为真实模型调用。真实模型的
显式手动基准由
`backend/scripts/run_luxian_0609_consultation_synthetic_benchmark10.py --real-model` 提供；详见
`docs/acceptance/2026-09-05-consultation-family-performance-replay.md`。它固定 1 次预热和 10 次
正式轮次，并只用合成资料。Prompt 只在单次进程内逐字比较，输出仅保留一致性和长度，绝不
输出 Prompt 或持久化摘要。2026-09-05 已完成一次真实模型采样，逐轮统计和适用边界已记录在
上述性能复放文档；它建立当前夹具基线，不替代同输入的跨版本 10% 对照。
