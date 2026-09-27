# 原始0609执行、发布、保存与读取链路验收

## 范围与基线

- 分支：`codex/lx0609-publish-read-chain`；独立工作树 `lx06-chain`。
- 固定基线：`07a1396d2438bb52a4ba9bb481c5b5de0e6523a6`。
- 只验证原004抢救记录时效（`LX0609-09-01-01`）与原023会诊建议执行（`LX0609-03-01-04`）。沿用原001–075空资料三入口测试作为相邻保护。
- 不修改医学判据、Prompt、模型、执行器、并发配置，不处理82项历史测试归因。未修改或合并Claude工作树。

## 已复现的问题与最小修复

1. `SichuanQCService`生成`evaluation_results`时遗漏已有的`customer_text_seal`及显式结论文案；批任务装配也遗漏同样字段。正式结果落盘后丢失发布证明，批详情进入旧文案处理路径。
2. `custom_qc_workspace_service._explicit_customer_text`即使保留已发布文案长度，仍通过`_safe_text`压平换行。实际抢救、会诊不合规建议在批详情变成一行，与落盘和latest-result不一致。
3. 仅在上述两处搬运已有发布字段；不重新签章。DTO对正式已验证文案保留原始换行，敏感信息检查、旧结果裁剪保持原样。

修复前非空链路测试复现建议逐字不一致；只修DTO仍失败，直到补齐服务返回和任务装配两处透传才通过。三个生产文件合计小范围字段搬运修改，没有新增抽象或公共判定层。

## 验收方法

测试：`backend/tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py`。

- 三入口：单病历批任务、病历池两份批任务、客户样本池任务。
- 保留正式API创建、后台任务调度、EvidenceSession、原生执行器、裁决/发布、实际SQLite写入和HTTP读取。
- 医院物理取数用合成资料；模型只替换传输响应；不使用真实患者或客户数据库。
- 捕获聚合器入口的真实裁决状态/原因与出口发布结果；独立数据库连接读Envelope JSON，再重建服务读取latest-result和批详情。
- 对比状态、原因码、完整公开事实、证据内容/坐标、结论和建议；仅归一化既有别名、空数组省略以及受控文书ID的HMAC脱敏引用，不忽略文案差异。
- 验证发布证明在任务结果和落盘中保持原值。
- 原004覆盖6小时内完成、超时、缺结束时间、超时与缺时间混合；模型调用为0。
- 原023保持固定响应及原有2次调用、每次17输入+5输出Token断言；覆盖串行、显式并发和默认并发，增加非空结果实际落盘及两类API读取断言。

## 测试隔离修正

原三入口夹具漏替换`sample_programmatic_evidence`的源表/详情回读，曾尝试访问默认数据库；现只替换这两个医院资料读取边界，并禁止测试连接默认数据库。会诊事实冻结缓存改到每个测试的临时目录，避免重复运行跳过模型桩。首次失败是夹具隔离缺口，不作为生产数据库缺陷。

## 验证结果与边界

- 三入口链路10项通过，包含最终发布证明透传断言。
- 相邻Canonical交付、读取投影、HTML导出三个文件142项通过。
- 前端Lint（`npm run lint -- --no-fix`）、类型检查通过；单测124个文件、1067项通过（`--maxWorkers=2 --minWorkers=1`），未修改前端。
- 编码检查通过。Ruff检查中三个改动文件无问题；`sichuan_qc_service.py`剩余7项与基线源码stdin检查一致（2项F401、4项F541、1项F841），没有扩展清理。
- 首次相邻回归71项失败发生在测试服务初始化连接默认PG；直接用SQLite URL仍携带PG专用参数，随后引导SQLite连接又碰到PG专用ALTER语法。最终复用集成测试相同环境边界：独立SQLite engine/session、跳过PG旧表迁移（新表包含全部列），142项通过。没有把这些环境失败计为产品缺陷或修改对应测试断言。

相邻测试复现：在backend中用Python启动，先设置空`DATABASE_URL`、测试`JWT_SECRET`和`DB_SCHEMA_MODE=single`；导入`app.database.connection`后把其`engine`替换为新建临时文件SQLite engine、`SessionLocal`替换为该engine的sessionmaker；再导入workspace模块，仅将`_sync_batch_job_parent_columns`设为无操作，随后`pytest.main`运行：

```text
tests/unit/test_luxian_0609_canonical_result_delivery.py
tests/unit/test_luxian_0609_read_side_projection_boundary.py
tests/unit/test_custom_qc_workspace_export_html.py
```

三入口测试本身包含完整隔离夹具，可使用不可连接的测试PG URL初始化（夹具禁止默认连接），运行`pytest -o addopts='' -q tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py`。过程日志和独立SQLite留在`.tmp/0910-full-audit/`，不提交。

这是本地合成输入、固定模型响应、SQLite与进程内HTTP验证；不等于客户PG、真实模型泛化、跨进程重启或完整原始质控集临床验收。未推送、未合并、未发布客户版本。

## 后续变更（2026-09-26）

按用户决定取消 LX0609 结果文案签章。本文中“发布证明”的透传与断言已移除：服务层仅对 v2 正式结果透传结论与建议，Worker 原样搬运；三入口验收改为断言全链路不出现签章字段，并补充超长多行文案、废弃签章字段忽略、非法状态/缺事实经正式 API 拒绝、病例集合错配保存拒绝。多行与长文案保留、三入口实际保存与 API 读取、测试数据库及会诊缓存隔离保持不变。
