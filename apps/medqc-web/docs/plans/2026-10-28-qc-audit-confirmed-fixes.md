# 质控独立审核确认问题修复

## 范围与边界

- 固定基线：`f97ae1b6ce5f20e8da3ced7903d54007d1c148c6`。
- 工作树：`C:\medqc-qc-audit-fixes-20261028`。
- 分支：`codex/qc-audit-fixes-20261028`，没有修改业务集成分支。
- 五组 `gpt-5.6-sol / high` 分别处理输血、保存与选轮、材料有效性、冻结复用、演示展示；测试因内存限制串行运行。
- 仅处理首轮确认的九项问题。机构授权、模型身份失效、并发缓存 CAS 等审计疑点不冒充已修复。
- 不连接业务库、不调用真实模型、不启动质控任务、不重跑27份；不重启当前服务、不部署。

## 修复内容

| 审核项 | 修复及保护条件 |
| --- | --- |
| 输血后评价遗漏无结束时间事件 | 每次实际输血以稳定文书引用关联，缺结束时间的事件保留资料缺口；不再混用过滤后数组和原事件位置。 |
| 局部关联歧义掩盖确定缺失 | 将评价歧义限制在真实候选事件；其他事件已确定的缺评价仍为不合规。同一事件的未知时间、冲突仍保护为资料不足。 |
| 作废文书进入规则 | 页面、Bundle、Snapshot/native/runtime/timeline 共用 LIMIT 前过滤，保留状态字段；仅精确排除明确无效状态，Save、空值、未知状态继续保留。有效PDF不会因已作废原文书而被同时排除。 |
| 精准补跑中断后成功项不可读 | 顶层 `items_json` 是本轮成功项权威来源；保留摘要结构、三坐标、冻结规则范围、重复、状态及成功/失败互斥校验。不拼旧轮、不重判。 |
| 单条和批量最新结果选轮不一致 | 最新结果导出显式纳入同轮部分失败结果，复用选轮器与代次歧义保护。局部任务不覆盖全量；完整性按所选任务冻结范围。导出明确标注未全部完成。 |
| 自动重试计划冒充已排队 | `planned` 只表示计划，CAS入队成功才是 `queued`；领取后 `running`，入队失败为 `enqueue_failed`，执行中断为 `interrupted`。后两者停止自动轮询并保留成功项。 |
| typed会诊第二阶段不冻结 | typed decisions 与 legacy results 必须唯一、完整覆盖计划规则，typed状态复用既有 reducer；有失败或缺项不提交冻结。 |
| 专项核验失败回退被永久冻结 | 06-01-02/04/05 显式记录专项完成性。当轮主抽取回退口径不变，但未完成专项不冻结整批。仅升级相关冻结键，保留其他缓存兼容。 |
| 演示实时栏显示非确定结论 | 复用现有可见性策略，仅过滤实时结论展示，筛选后取最近六条；sync_admin全量可见，任务统计及失败提示保持真实。 |

## 缓存兼容与上线注意

- Bundle选择协议由v6升至v7，无数据库表结构迁移；旧版本兼容读取，正常加载入口按需重组并更新缓存。
- 本轮没有调用业务Bundle加载/刷新入口。以后启动并读取业务材料时，现有加载逻辑可能写入重组缓存，不能称为纯只读上线。
- 三条检查专项的旧主冻结文件保留但不再命中新键；其他冻结键不变。下一次用户授权的实际质控可能重新核验相关专项。
- 不删除原始文书、PDF、冻结文件和成功质控结果；不自动修复任何客户机历史任务。
- 目前没有院方完整文书状态字典，不将草稿、退回或模糊包含词自行映射为作废。

## 验证方法与限制

后端采用无部署 `.env` 的独立工作树、临时SQLite、固定应答和合成材料。测试隔离器禁止普通网络连接；仅放行Windows事件环创建私有socketpair所需的同步回环连接。测试可写临时SQLite与临时缓存，不能连接业务PG或模型端点。

验证重点包括：正式执行→Binding/Reducer→Finalizer→SQLite保存读取；精准重试启动后异常、CAS迟到回调及批量导出；材料有效性及旧Bundle失效；两轮失败恢复与冻结命中；演示/开发权限及真实重试提示。

定向测试共482项通过（重复运行不叠加计数）：

| 组 | 最终通过 | 主要证据 |
| --- | ---: | --- |
| 输血关联与047 | 87 | 缺结束时间事件在首/中/末；显式/泛指评价；局部歧义与未知时间；正式执行、Binding、Finalizer、SQLite回读。 |
| 保存、选轮、重试、导出 | 72 | 重试策略14，SQLite持久化36，导出8，worker恢复/耗尽2，Canonical/bulk12。最终中断原因码调整后完整复跑36项通过。 |
| 材料、源读取、基本时效、缓存及冻结 | 218 | 真实SQLite谓词、页面/Bundle/Snapshot选择、旧缓存失效；标准asyncio事件环下的固定应答与冻结复用。 |
| 前端实时展示和重试状态 | 105 | 展示39，重试状态及抽屉66；单worker，覆盖受限账号和sync_admin、不修改原任务、非活动重试不轮询。 |

后端复测从仓库根使用本轮私有隔离器：

```powershell
py -3.10 -B apps/medqc-web/.tmp/0910-full-audit/audit-fixes-20261028-private/run_isolated_tests.py tests/unit/test_transfusion_association.py tests/unit/test_luxian_0609_transfusion_performance_043_047.py
py -3.10 -B apps/medqc-web/.tmp/0910-full-audit/audit-fixes-20261028-private/run_isolated_tests.py tests/unit/test_qc_partial_failure_persistence.py
py -3.10 -B apps/medqc-web/.tmp/0910-full-audit/audit-fixes-20261028-private/run_isolated_tests.py tests/unit/test_validation_material_selection.py tests/unit/test_luxian_0609_source_evidence_reader.py tests/unit/test_luxian_0609_native_basic_timeliness.py tests/unit/test_bundle_scene_cache_fallback.py tests/unit/test_luxian_0609_second_stage_freeze_completion.py
```

隔离器属于本机私有工具，不提交；正式CI应使用其自己的测试数据库隔离配置。首次测试遇到的Windows事件环socketpair拦截及SQLite清理文件锁已在隔离器修正，最终相关测试进程退出码0。

静态检查：编码和diff检查通过。修改Python文件的Ruff仅报告assembly.py的4项既有问题，已在固定基线逐项复现（F401、F841、两处F402）；本轮没有新增Ruff问题。修改前端文件只读ESLint通过；提交前另执行一次全src只读lint，0错误、3401条样式告警，未批量自动修复。测试仍有既有Pydantic弃用和抽屉替身警告。

未进行真实病例模型运行、客户机验收、浏览器验收、业务库回放或全部规则回归。内存一度不足1GB，未运行完整类型检查与全量前后端单测。也未离线回放患者私有原始应答，本轮复用仓库材料夹具、固定应答及审核合成反例。不能据隔离测试宣称客户机历史失败已经恢复，也不能宣称全部质控规则完成准确性验收。
