# 1026材料与适用性审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 1026新任务保存不可变材料及不适用来源回执，旧任务仅只读标注。
**Architecture:** 同事务捕获登记及真实读取，复用case_material owner；审计receipt由实际消费来源生成并严格安全投影。
**Tech Stack:** Python/SQLAlchemy/FastAPI/合成数据。
**Spec:** 本会话授权，基线a5123098b，独立分支codex/1026-task-source-20261114。

## Global Constraints

不读真实库/患者材料，不改配置、不调用模型、不跑质控/27份，不合并部署。原运行冻结目录保留不提交；普通CDM/无首页/身份来源完整性/历史/手术输血暂停保留。

- [x] PDF捕获+登记aux同事务冻结、读取不回查、坏损/身份/旧材料缺失拒绝。
- [x] NA实际来源完整性准入和安全回执，不伪造无事件文书；未知/截断gap，技术拒绝。
- [x] 信封/DTO保留receipt与材料指纹，旧结果只读标not_retained不回填。
- [x] 定向验证、独立复审、统一提交，不推送。

## 完成记录

- PDF捕获：登记和正文同一REPEATABLE READ只读连接，schema和业务源绑定；无首页物理依赖，缺三键列失败关闭。辅助登记/原文书ID/复核过滤一并冻结，不读取原始PDF文件。
- 冻结回放：源/身份/完整性严格校验，PDF重试先验证lineage和原材料，跳过当前登记及collect/hydrate；保留原始隐私身份字段。历史原文缺材料明确拒绝，结果仍可显示未保留标记。
- NA：实际消费来源完整零行允许无事件；缺供给、截断、未知范围data_gap，查询错误technical。无事件不伪造文书引用，安全receipt保留来源观察和受控事实摘要。
- 持久与交付：worker增量/最终绑定材料指纹，摘要/信封/单病历/review DTO均保留并验证receipt；旧结果仅投影标注，不回填或写库。

## 定向验证（集合可能重叠，不合计总数）

- 新PDF测试最终20 passed；之前PDF+failed_rule_retry+lineage组合78 passed，最后新增身份恢复和来源约束仅补跑PDF20。
- PDF辅助冻结新测试6 passed，selection/display/programmatic既有回归95 passed。
- NA receipt新增17与binding22合跑39 passed；finalizer既有70 passed。
- 根新增历史审计/投影/SQLite信封读回与篡改拒绝16 passed。历史当前登记依赖及单病历丢审计字段均有红绿证据。
- canonical交付、缺信封不回退、HTTP历史快照边界17 passed；新增store读取验证后相关canonical节点14 passed。
- 新PDF早期捕获5项先红后绿；旧“PDF不捕获”断言更新为无业务源严格拒绝。一次组合63 passed/4 fixture failures，后者为合成业务engine.url夹具缺失，未计通过；辅助代理补齐合成business_source URL夹具后，仅aux文件定向6 passed，4项失败已闭合；未重复95项集合。

## 独立复审

未参与实现的两名代理分别复审材料捕获/来源和NA/持久化/读取链。发现并闭合历史GET当前登记依赖、receipt材料绑定、单病历/review字段丢失、重试当前源回查及身份脱敏集合缩小。最终无剩余可确认P1/P2。

## 85c4d9a24复审P2补修

- 复核确认：PDF重试原材料校验发生在worker之前，原快照缺失/损坏/异源异常会逃逸，排队任务无法收尾。
- bound_job仅捕获该前置调用的MaterialSnapshotError；通过安全白名单投影保存任务级material错误与retryable=false，未知异常文本收敛为material_capture_failed。不捕获worker执行异常，不查询当前材料。
- 仅对观察时queued且具有原始filters的任务调用失败入口，沿用queued_only与原filters CAS。运行中、新filters、completed/failed状态不被迟到错误覆盖。
- 新增实际service+内存SQLite合成回归先10失败复现；修复后4个迟到保护+原PDF20+旧来源失败1通过。6个错误收尾断言初次因测试datetime序列化失败，修正断言后仅复跑这6项通过；合计31个不同用例通过，未重复其他集合。
- 未验证真实PG/队列并发，未读真实材料、连接业务库、调用模型、运行质控或更改旧任务。
- 补修独立复审另发现非LX0609任务的原filters未进入UPDATE条件；现对携带expected_queued_filters_json的queued_only写入统一增加原子WHERE约束。新增SELECT/UPDATE间同连接变化合成用例确认失败UPDATE命中0行，service回滚；不冒充真实PG并发验证。该用例首轮因忽略回滚而错误期待注入变化保留，修正断言后单独通过。新增收尾10项及既有CAS2项在最终服务代码下通过，未重复PDF集合。
- 最终独立复审确认P2闭合，未发现剩余P1/P2；复用定向结果，未重复测试。diff、语法及UTF-8无BOM/LF检查通过。

## PR65 CI补修

- e8a5ea423远端质量门12失败：5项检查/检验NA的query_version校验因receipt早期import函数别名不跟随注册表合成替身；改为同一注册表模块调用，不增版本/来源白名单。receipt测试先导入、再运行该组替身用例34项通过，未知版本拒绝负例保留。
- 2项mainline旧断言要求完全没有fact_refs/空refs，与安全审计回执合同冲突；改为顶层不暴露内部字段、嵌套receipt精确绑定观察摘要，不允许虚构客户文书证据。
- 代码缺陷：会诊023条件不满足、025无事件/非适用、021无申请丢审计依据（含2项合成基准中止）；仅映射实际核验文书或本快照空来源观察。025新NA路径的绑定错误与原路径同样受控转snapshot_mismatch。
- 输血无事件分支原来附带尚未使用的horizon/评价依赖，改为保留实际触发来源，043/047继续包含实际检查的普通/上级病程和两类医嘱；不改分类函数或暂停策略。
- 初始定向复现7失败/2通过（检查用例单跑通过而组合CI失败，归因导入时机）；后续直接合成replay复现021空依据异常。修复后：相关receipt/检查/会诊/输血正负例34通过；主链旧断言、历史投影、重试收尾等32通过；合成基准文件6通过。025绑定异常负例与入口相关5通过。集合有重叠，不累计，不重跑全量。
- 合成基准仅脚本固定响应替身，无真实模型或真实病例质控。原1026捕获、重试CAS、历史结果/快照、无首页取材及手术输血暂停未放宽。未验证真实PG并发或真实队列。
- 最终独立复审无可确认P1/P2，确认实际审计依据、025绑定拒绝及分支依赖保护，未重复测试。

## 限制

本轮仅合成数据与内存SQLite、受控SQL事务替身，未运行真实隔离PG的RR并发/权限验证，未实测完整真实队列或浏览器链；没有读取真实任务或材料、调用模型、重跑质控或27份。冻结观察仅unavailable时不能细分缺表与未供给，不从未绑定当前上下文猜测原因。已保存历史结果不补证/重算。本地运行生成freeze目录保留且不提交，未重启本地API。
