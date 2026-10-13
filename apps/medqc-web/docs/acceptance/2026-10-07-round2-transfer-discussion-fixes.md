# 第二轮转科与疑难讨论触发修复（2026-10-07）

修复基线为`57b863d2b328b2d93b004ffb6e49da55be76d804`。处理独立审计已确认的两个合成误报：计划但尚未实施转科被072/073判漏文书；入院时诊断不明确但当前已明确被050判漏讨论。未改050临时业务口径、合同、Renderer、保存层或其他规则。

## 改动与职责

- `extended_document/transfer_documentation.py`：转科医嘱按分句识别；明确计划、否定或条件尚未成立的分句不触发。另一分句写当前已转科时仍触发，普通“转科”“转入ICU”保持有效。
- `extended_document/difficult_case_trigger.py`：仅排除紧邻“入院时/入院初/既往/此前/先前”且后文明确当前诊断已解决的那一处诊断不明。其他当前或未明确解决的不明表述继续触发；同文书另有当前仍不明确不能被历史解决声明抵消。
- `native_extended_document_execution.py`：本代理只增加上述helper导入并替换050的strong_uncertain_rows单个条件。抗菌及065分支由其他代理并发维护，已协调边界；未全文件格式化或回退他人改动。

这是对已经证实的明确语言边界的局部修复，不声称所有自由文本计划、否定、时间关系均可解析。050仍只消费既有标记与入院7天后文书，不扩大“诊疗方案难以确定”的批准范围。

## 红绿验证

独立测试文件：`backend/tests/unit/test_luxian_0609_transfer_discussion_trigger_boundaries.py`。

1. 修复前：9 failed、12 passed；失败为计划/条件/否定转科以及当前已解决的历史诊断。首次收集因测试函数漏接rule_id参数失败，修正测试后重新得到真实业务红灯，未把收集错误当红测试。
2. 局部修复后：21 passed。
3. 原执行器文件与新文件聚焦筛选`050 or 072 or 073 or transfer or uncertain_diagnosis`：46 passed、389 deselected。
4. 四个涉及文件Ruff通过。
5. 原私有冻结反例重放：计划转科072/073、历史已解决050共3结果从non_compliant变为not_applicable/trigger_absent_complete，模型调用0。既有“拟转科”、当前明确诊断控制保持not_applicable，两项来源不可用控制保持data_gap/source_unavailable。
6. 已取材的真实C04/C25通过正式EvidenceProvider→执行器→绑定归约重放：4条结果仍为data_gap/association_failed，未确认医生漏写。并非PG新取材或新正式任务。

命令：`python -m pytest backend/tests/unit/test_luxian_0609_native_extended_document_execution.py backend/tests/unit/test_luxian_0609_transfer_discussion_trigger_boundaries.py -k "050 or 072 or 073 or transfer or uncertain_diagnosis" -q --tb=short`，设置PYTHONPATH=backend。

私有原始基线文件保留；新增`fix-red-private.txt`、`fix-green-private.txt`、`fix-focused-private.txt`、`fix-replay-private.py`、`fix-results-private.json`、`fix-verify-private.py`、`fix-verification-private.json`位于`.tmp/0910-full-audit/round2-transfer-discussion-private/`。不提交这些原文证据。

## 限制

未覆盖真实计划转科医嘱或真实050适用病例；未运行UI/保存/真实模型/全仓测试，不批准上线。051两条候选观察（评价终点以后的讨论、未知时间讨论与晚讨论并存）没有纳入本次修复。071未追加验证。此次无模型调用、无PG写入、未提交推送或重启服务。

## 交叉审查补修：禁止跨问题抵消

协调者发现第一版helper跨全文寻找解决声明，导致追加“另一疾病目前已明确诊断为高血压”即可把当前原因仍未查明改成不适用。补充5条正式执行器反例/控制，修复前4 failed、22 passed，证实回归；没有将旧绿结果当作最终验收。

现将解决声明限定为历史不明表述后紧邻的逗号分句，且分句须直接以“现/目前……诊断已明确”等同问题承接语起始。明确“另一/其他/合并/并存”对象不解除原问题；后文仍存在“至今/目前/仍/尚/依然……未查明/未明确/不明/难以确定/待查”时保留原触发。此守卫只决定是否允许消除已有的历史标记，不新增诊疗困难独立触发口径。

补修后独立26项全部通过、Ruff通过。原始正例“入院时不明，现已明确诊断……”仍不适用；当前仍不明确控制保持不符合。日志为`fix-cross-red-private.txt`、`fix-cross-green-private.txt`、`fix-cross-focused-private.txt`。未调用模型、写PG、修改共享规则分支、提交或重启。
