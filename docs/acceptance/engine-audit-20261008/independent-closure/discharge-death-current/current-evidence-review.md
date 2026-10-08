# DD原11合成观察当前版本证据绑定

当前受限复验11/11符合原人工预期，attempt5退出0。责任源固定56322bcffa32ac33b5069975f1dbf3af18b597ac，实际执行HEAD为21f4a93e103a34002a1f9d36f9d895f226c0122f（仅两台账文档提交）；责任源和加载/读取的142个仓库源码/静态数据条目均与固定git blob一致，执行前后HEAD及责任SHA不变。

只复用原DD-001..007及DD-028..031的合成输入与医学预期，输入中datetime/tuple/frozenset原类型保持；原冻结、原probe和历史结果未改。每节点输入、原预期hash见冻结文件与实际结果。历史观察仍没有可追溯source/execution manifest，本轮是独立当前证据，不补造旧执行SHA、不全量重审，不作临床验收。

层级严格为7个061时限纯函数及4个068真实原生执行→决策绑定/归约→Canonical。068保留原llm_client=None、实际llm_call_count及tokens均0。customer_rule_package为模块初始化替身：仅从固定声明blob AST.literal_eval读取RULE_FAMILY_DEFINITIONS原tuple，提供原始常量；不抽取/改写任何生产函数。不验证该包完整初始化，不验证API/保存链。此隔离同已成功surgery060 prepared-runner-v1，原因是contracts只需族声明却连带初始化批量复核/SC发布目录旁支。

最终guard env/网络/DB/外部写入/非精确git进程/非源码仓库读取触发均0、阻断路径为空；dotenv no-op 1次。仓库读仅.py源码及5个精确静态规则JSON，未放开data目录/患者材料。禁仓库pyc写入，采用独立空cache前缀读真实源码。Windows平台标准库预缓存在项目保护前按root授权完成；之后外部进程仅固定read-only git命令的list2cmdline精确集合。未连接PG、调用真实模型或读取.env/真实病例。

前四轮完整保留：attempt1在stdlib Windows平台探测NUL上0节点阻断；attempt2缺master精确白名单0节点阻断；attempt3有7纯函数符合、4导入guard错误，收尾Windows audit argv字符串格式造成git误拒；attempt4完成来源绑定并定位4条同一sc146_intrinsic_launch_tiers.json旁支阻断。四条probe_error均为基础设施诊断，不作产品失败，不改原答案。此前静态“5JSON足够”结论因遗漏contracts本地customer_rule_package导入链而不足，已据attempt4真实trace更正；不以持续增加静态白名单解决，改用声明初始化隔离。

|节点|原场景|原预期/当前实际|层级|
|---|---|---|---|
|DD-001|exact24|compliant / compliant|纯函数|
|DD-002|24plus1sec|non_compliant / non_compliant|纯函数|
|DD-003|negative_interval|data_gap / data_gap|纯函数|
|DD-004|missing_completion|data_gap / data_gap|纯函数|
|DD-005|empty_source|data_gap / data_gap|纯函数|
|DD-006|death_confirmed|not_applicable / not_applicable|纯函数|
|DD-007|conflicting_discharge|data_gap / data_gap|纯函数|
|DD-028|senior_approval|compliant / compliant|真实执行→绑定→Canonical|
|DD-029|ordinary_doctor_only|data_gap / data_gap|真实执行→绑定→Canonical|
|DD-030|undated_approval|data_gap / data_gap|真实执行→绑定→Canonical|
|DD-031|source_unavailable|data_gap / data_gap|真实执行→绑定→Canonical|

关键SHA：

- `frozen-11-original-inputs-expectations.json`：`966242f69656a3b37435bcfe2ecaf2be498dacdceaec8ba0431f2591941cedb3`
- `current-responsibility-source-manifest.json`：`f51cbc2edb5ded6315add0db6ac693784073bce21ce37082c4dcce29153b0303`
- `attempt-3-static-data-source-manifest.json`：`f2f8d1e0f49485d68fb7388a4d61af8d6b7088bf452441cc8351c89aa1e03f7a`
- `attempt-5-declarative-module-source-manifest.json`：`412c1f878f9c0f0cd11bd4e859c259223745aa70ed4329ef1f1650cbaf33de36`
- `independent-current-11-attempt-5-runner.py`：`845d4774221fc2cc732a04c0ccf624e512e702dd4be278f3b91405e7808ff60b`
- `current-fixed-56322-attempt-5-results.json`：`b3050a25d13e185a630f080ec037c52583720adecc5c0c0f057d286ac7944f80`
- `attempt-5-console.txt`：`5b0de4df3673c85fc3e8f1aa0dda51cd852c0c3a413a48d2c2b20446922b3da7`
