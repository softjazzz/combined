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

## 限制

本轮仅合成数据与内存SQLite、受控SQL事务替身，未运行真实隔离PG的RR并发/权限验证，未实测完整真实队列或浏览器链；没有读取真实任务或材料、调用模型、重跑质控或27份。冻结观察仅unavailable时不能细分缺表与未供给，不从未绑定当前上下文猜测原因。已保存历史结果不补证/重算。本地运行生成freeze目录保留且不提交，未重启本地API。
