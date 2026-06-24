# SC146 probe vs random10 运行态差异诊断报告

生成时间：2026-05-21 00:33:02

## 结论

- standalone probe-like 运行次数：1。
- random10-equivalent（只跑 2013648/SC-146，复用正式 random10 postprocess/adjudicator mode）运行次数：3，通过 3/3。
- 本轮未继续 random10，未扩大到 20 份，未写正式 QC 结果表。
- provider_error 现在只代表真实 provider/连接/限流类错误；parse/missing/schema 类终态不再混入 provider_error。

## 调用参数对比

| run                            | attempt | model           | pack_concurrency | strict_json | compact_context | prompt_hash      | prompt_chars | targeted_hash    | missing | status             | provider | technical |
| ------------------------------ | ------- | --------------- | ---------------: | ----------- | --------------- | ---------------- | -----------: | ---------------- | ------- | ------------------ | -------: | --------: |
| standalone_probe_like          | 1       | qwen3.5-35b-a3b |                1 | True        | True            | dde06c9bcd28af17 |         4878 | 8465248c6558615d | []      | rejected_by_system |        0 |         0 |
| random10_equivalent_sc146_only | 1       | qwen3.5-35b-a3b |                3 | True        | True            | dde06c9bcd28af17 |         4878 | 8465248c6558615d | []      | rejected_by_system |        0 |         0 |
| random10_equivalent_sc146_only | 2       | qwen3.5-35b-a3b |                3 | True        | True            | dde06c9bcd28af17 |         4878 | 8465248c6558615d | []      | rejected_by_system |        0 |         0 |
| random10_equivalent_sc146_only | 3       | qwen3.5-35b-a3b |                3 | True        | True            | dde06c9bcd28af17 |         4878 | 8465248c6558615d | []      | rejected_by_system |        0 |         0 |

## Hash 汇总

- first_pass_prompt_hash：dde06c9bcd28af17。
- targeted_evidence_context_hash：8465248c6558615d。

## 差异定位

- 单独 probe 与 random10-equivalent 的核心差异保留在 `run_label`、`pack_concurrency` 和 postprocess/adjudicator `mode`；两者均使用 `SC-146` strict JSON prompt 与 compact evidence context。
- 若后续完整 random10 仍失败，应优先排查多 pack 并发带来的 provider 队列/响应漂移，而不是 SC-146 单规则 prompt 是否缺失。
- 当前 2013648/SC-146 定向门禁要求为 3/3 completed、provider_error=0、technical_error_internal=0、missing_rule_after_retry=0、parse_error=0。
