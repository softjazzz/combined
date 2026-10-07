# 抢救时间及输血实施门控工程修复（2026-10-07）

对应独立审计 RSC-01、T-01；本轮只修执行器，不改医学判据、Prompt、目录或发布范围。

## 复现与修复

通过正式 typed 执行器和 reducer 新增合成断言，修前抢救 6 项、输血 3 项失败，同跑既有保护项 79 项通过。抢救使用受控 FakeLLM，正确返回本次时间 absent；输血使用合成 EvidenceReadSession、无模型。

- 抢救：标签时间增加所在句的计划、既往、否定、条件语境排除，不再将其补成 present；保留真正本次标签纠正模型漏抽的能力，不修改另外五项。
- 输血：专用 documents 快捷路径与来源行路径共用局部排除；明确取消或未实施不再凭长度触发已实施。仅取消正文但未证明完整实施事实时保留 data_gap；不推断为 not_applicable。结构化实施、另一份实际记录仍可触发实施。无输血反应、未输血前检查不否定实施。

## 验证

在 backend 执行：

```powershell
python -m pytest tests/unit/test_luxian_0609_rescue_record_completeness.py tests/unit/test_luxian_0609_transfusion_performed_gate.py tests/unit/test_luxian_0609_native_transfusion_execution.py tests/unit/test_luxian_0609_native_transfusion_freeze.py -q --tb=short
python -m ruff check app/services/luxian_0609/rescue_record_completeness.py app/services/luxian_0609/native_transfusion_execution.py tests/unit/test_luxian_0609_rescue_record_completeness.py tests/unit/test_luxian_0609_transfusion_performed_gate.py
```

最终 211 项通过（抢救80、门控12、输血执行116、冻结3），Ruff通过。既有弃用警告15项。抢救新增边界每例保持一次受控调用，无新增模型阶段。门控使用 llm_client=None。没有 PG 写入、真实模型调用、保存/API/浏览器验证、提交、推送或服务重启。pytest应用导入初始化既有本地SQLite demo库，不是临床PG运行。

## 限制

这是合成机制修复与保护集回归，不能替代真实适用病例验收。既有长且语义不明的专用输血文本门控沿用原行为；本轮不建立全面输血事实抽取器，不将未知扩大为未实施。相同文书同时有取消和实际实施的复杂冲突仍保守不凭长度确认，结构化实施与独立实际文书可保留实施证据。

旧审计独立脚本本轮启动未及时完成，不计为本轮成功证据；采用上述可断言的正式入口单测完成红绿验证。CodeGraph目录存在，但 explore 返回 unable to open database file，采用源文件定位。

## 交叉审后否定反应保护

交叉审发现“没有输血反应/没有输血不良反应”被非实施正则误截。新增正式typed链断言，用07-02-02是否继续进入实施分支隔离门控；无结构化实施来源。修前2失败、15通过，限制否定宾语不匹配输血前、输血反应及输血不良反应后17项全部通过，相关Ruff通过。保留未发生/未见/无反应、明确取消、仅申请、未知文本、查询失败与实施对照。仅跑门控专属测试，未宽跑全量。

额外发现现有07-02-01后续内容判定对“本次输注红细胞2U，输注过程平稳，无输血反应。”仍给data_gap，虽实施门控正确；该后续语义规则未纳入本次门控修复，不把它计为本轮修复通过。
