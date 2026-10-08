# RR-M01 独立复核：074权限合同漂移关闭

固定提交 `b85b49882bcdab5703ddacf54225c671bac353da`，父 `0628782191861460bbf24edbf848eb601829876c`。本组独立复核接受 **RR-M01工程合同关闭**。不据此宣布临床准确率或生产交付通过。

执行前预期冻结在 expectations.json，复用原M01合成事实和固定响应观测。完整JSON比较确认主合同整文件不变，扩展合同只改074的 `decision_authority=program_then_optional_llm` 和 `max_llm_calls_per_rule=1`；目录只给074写入既有 `lx0609_diagnosis_change_documentation_v1-quote-2026-10-07` 版本。其他规则条目、顺序、字段不变；执行器、抽取器（包括Prompt正文）、加载器和发布范围模块与父提交blob相同。共7项静态检查通过，详见static-review.json。

收到独占测试槽授权后执行runtime_probe.py，4.13秒、exit0：

| 冻结检查 | 实际 | 结论 |
| --- | --- | --- |
| LOAD | 实际编译合同 `program_then_optional_llm/1`；executor `extended_document`、mode `native_async`、golden `pending`；目录及加载Prompt版本一致 | 通过 |
| M01 | 同份显式修正诊断原文的理由/依据均有效，`compliant/requirement_satisfied`，一次Fake响应，调用1≤预算1；调用参数2048上限、allow_length_retry=false | 通过 |
| EMPTY | 完整来源空，`not_applicable/trigger_absent_complete`，调用0 | 通过 |
| NEGATED | “继续观察，无需修正诊断：甲病。”，`not_applicable/trigger_absent_complete`，调用0 | 通过 |

使用固定提交的完整原生模块、既有合成来源行fixture、固定Fake客户端以及事实绑定/归约；逐文件与git blob核对，没有AST截断或算法重写。禁止dotenv及socket/httpx外连，DATABASE_URL置空，不导入app.main，不跑pytest；未读原病例、PG或.env，真实模型调用0。runtime-results.json包含实际状态、事实、Token、调用参数及加载合同。

本组没有重复132项开发测试，没有审查其他规则，没有修改生产或共享测试。测试槽在探针结束后立即释放。结论只覆盖原RR-M01权限/预算漂移；未知状态、模型失败、真实病例质量和完整交付路径仍遵循各自既有验收边界。
