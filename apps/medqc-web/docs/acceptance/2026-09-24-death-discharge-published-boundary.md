# 原始 0609 死亡与出院文书族已发布事实读取边界

## 问题与改动

死亡文书 051/060 及出院文书 061/062/063/067/068 的已发布 `customer_display_facts` 原来经 Finalizer fallback 再送内部投影。060 的额外私有文书 ID 会被静默去除；061 的公开 `actual_interval_hours=1.23456` 会再次舍入为 `1.23`。这使保存与读取值不一致，也掩盖已保存的污染。

本提交只在原有两个规则族模块各新增一个公开读取入口：

- `validate_published_death_document_facts(*, rule_id, raw)`
- `validate_published_discharge_facts(*, rule_id, raw)`

它们按各自既有可发布形态检查字段集合、基本类型和原来发布时已经要求的自洽约束；合法的已发布字典原样复制返回，非法值返回 `None`。没有再调用 `_safe_051`、`_safe_060`、`_safe_061` 等内部投影。内部发布函数、执行器、Prompt、模型参数、医学状态与证据链均未改。死亡模块新增 70 行、出院模块新增 138 行，职责仍在原规则族事实合同文件，无新框架。

## 兼容性重点

- 051 的时间窗口 `remaining_seconds` 在首次发布时可能从数值转为整数，读取只接纳已发布的整数；051 时限、逾期缺失、时间窗口未成熟、观察截止缺口四种输出均保留。
- 060 有/无死亡时间两种形态均保留；额外 `source_document_id` 不再在公开读取时静默消失。
- 061 包括正常时间差、权威时间冲突、缺时间、不同时间来源；负一秒的 `actual_interval_hours=-1/3600` 原值保留，不舍入成 `-0.0`。正数保持已有两位小数的已发布形态；非有限数、布尔值与过大整数受控拒绝。
- 062 抽取待定及药物缺项，063 诊断数据缺口及一致性，067 病程时间/正文缺口与存在性，068 批准时间缺口/批准存在/批准缺失均有固定已发布形态测试。067/068 正常路径仅要求原来允许的有序窗口，未强加“必须前一天”限制；时间缺口形态仍校验原来的前一日与当日窗口。

## 验证及接线

新专属测试及既有两个 mapping 测试共 79 项通过；原生 extended-document 的死亡/出院/出院前相关 47 项通过；改动文件 Ruff、`compileall` 与 `git diff --check` 通过。测试使用合成日期和固定输入，不使用客户数据库或真实模型。这证明模块入口与原生既有测试分别成立，**不代表生产读链已经接线**。

Finalizer 集成责任留给主协调：在 `validate_luxian_0609_published_customer_display_facts` 为上述规则号分别调用对应 `validate_published_*_facts`；`None` 转已有“解释合同不完整”受控错误；首次发布保持原 `safe_*` 路径，并在发布后 `finalize_luxian_0609_executor_customer_display_facts` 复用已校验的事实。接线后须重跑专属测试、两族 mapping、原生 extended-document 聚焦组，以及隔离 Canonical Store 的正常与污染读回。
