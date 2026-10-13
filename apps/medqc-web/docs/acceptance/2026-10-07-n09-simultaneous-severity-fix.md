# N09 同刻解除与重开修复

基线 `81f17237a960868695f135664acdece4b9e63af6`。按第五轮交接，仅修复008/009区间构造函数；未修改目录、Prompt、医学阈值、Finalizer或其他代理文件，未提交。

输入为08:00开始、10:00解除、10:00另行重开，随后至1/7没有病程。旧实现以start优先排序，忽略重开后又关闭整个区间，正式客户结果错误合规。不同来源行具有相同权威时刻时，现检测先后不可确定并返回既有时间资料不足合同，经执行器→Binding/Reducer→Finalizer交付 `data_gap / authoritative_time_missing`，不再擅自给事件排先后。并未把“同一分钟内不同时秒”合并为同刻。

生产变更仅 `backend/app/services/luxian_0609/course_quality/rules_008_009.py` 的 `_severity_active_date_intervals` 新增12行。相同已停止医嘱自身的start/end有明确生命周期关系，不视为跨行歧义；评价终点之后的事件不影响已关闭区间。

先红：新增专用测试21项，13失败、8通过。两规则×六种行序共12项原来均错误合规；隐式停止与另一行同刻重开1项也失败。正常控制8项已通过。

修复后：新测试与上一轮severity回归共30通过；原执行器测试按008/009选出85项全部通过（其余139未运行）。Ruff及git diff --check通过。新测试18项穿过正式snapshot→executor→归约→Finalizer，并断言0模型调用；其余3项覆盖区间函数生命周期/终点边界。

```powershell
python -X utf8 -m pytest backend/tests/unit/test_luxian_0609_n09_simultaneous_severity.py backend/tests/unit/test_luxian_0609_round2_severity_regressions.py -q --tb=short --disable-warnings
python -X utf8 -m pytest backend/tests/unit/test_luxian_0609_native_course_quality_execution.py -k '008 or 009' -q --tb=short --disable-warnings
python -m ruff check backend/app/services/luxian_0609/course_quality/rules_008_009.py backend/tests/unit/test_luxian_0609_n09_simultaneous_severity.py
```

Claude原探针仅替换失效的本机测试夹具绝对路径，原文件未动；适配副本和输出位于 `.tmp/0910-full-audit/n09-simultaneous-private/`。RC5/RC5b两规则均资料不足；RC4明确15:00重开仍不合规；解除无重开仍合规；空壳不合规、有效短正文合规保护均保持。额外一秒后重开控制仍保留重开区间。

局限：均为合成工程事实，不宣称当前PG真实病例已触发。没有真实模型、PG访问/写入、服务重启、全量测试或提交。pytest全局conftest有既有本地demo SQLite初始化日志；本轮未改变此测试基础设施。资料不足沿用既有reason_code，未新增医学解释口径。

源码与测试SHA256：

- `backend/app/services/luxian_0609/course_quality/rules_008_009.py`：`2faa3c759e786f86409866f5938f0f543e69ab2c8ec842baf2b87d2024d0d0af`

- `backend/tests/unit/test_luxian_0609_n09_simultaneous_severity.py`：`b3d79e615c112898a4c7b2d299383e868d0018bbb565b7359839940d7e5d3ee5`
