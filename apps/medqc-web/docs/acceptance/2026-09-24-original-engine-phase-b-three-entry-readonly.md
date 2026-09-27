# 原始 0609 阶段 B：三入口固定输入链路验收

本次只读审计以 `25f0f035c` 为生产代码基点，新增 `backend/tests/unit/test_luxian_0609_three_entry_readonly_probe.py` 作为可复跑探针。仅检查原始 001（`LX0609-01-01-01`）和 004（`LX0609-09-01-01`）；不改医学执行器、任务服务或规则目录，不访问患者库或真实模型。此记录承接 `2026-09-24-original-engine-phase-b-readonly.md`，不将阶段 B 整体标为完成。

## 入口和固定输入

探针实际调用 `qc_sichuan.create_workspace_batch_job` 两次，分别提交同一住院事件的单病历任务和含该事件的两病历任务；另调用 `qc_sample_pools.run_sample_pool_intrinsic_validation` 提交同一事件的客户样本单叶任务。它检查三个路由创建并保存的任务过滤器，再将各任务交给真实 `run_sichuan_workspace_batch_job`，调用真实 `SichuanQCService.evaluate_running_final_bundle_input`、`prepare_luxian_0609_execution` 和 Evidence Session。测试仅在鉴权、激活、后台调度、任务/样本持久化、来源表读取和 bundle 读取等外部边界使用替身。客户样本的分族父/子任务不在这次动态探针内。

固定任务时钟为北京时间 2026-09-24 12:00，首份病例三坐标为合成的 I001/P001/V001，入院时间为 2026-09-20 08:00；三入口使用相同的病历池源行和规则选择。来源表行为空且明确标记未截断，bundle 为合成文本，模型替身禁止调用。这只能验证传参与发布边界，不能证明两条规则的临床判定准确。

| 观察项 | 单病历 | 病历池批量首份 | 客户样本单叶 |
| --- | --- | --- | --- |
| 路由保存规则、版本、任务日期 | 001/004；`2026-06-09`；`2026-09-24` | 相同 | 相同 |
| 进入真实 `prepare` 的选中规则、评价日、逐病例 horizon | 与固定首份一致；评价日 `2026-09-24` | 与单病历相等 | 与单病历相等 |
| 进入真实 Evidence Session 的规则、评价日、horizon | 与 `prepare` 相等 | 相等 | 相等 |
| 首份结果状态/原因 | 001 `data_gap/authoritative_time_missing`；004 `not_applicable/trigger_absent_complete` | 相等 | 相等 |
| 设置与模型 | 每任务 Worker 读取一次设置，并将同一对象传至 `prepare`；0 次模型调用 | 同左 | 同左 |

第二份批量病例也走过真实 `prepare` 和 Evidence Session；本表只比较三个入口共同的首份病例。设置对象相等只在各自任务内成立，并不声称不同时间创建的任务共享同一冻结版本。初版探针的客户样本替身漏掉源行范围字段，造成样本评价时点缺失；改成三入口相同的完整合成源行后，差异消失。这是测试输入差异，不能归因为生产缺陷。

## 证明边界和阶段 B 剩余项

这项测试证明相同新任务输入经过三条实际路由及共用 Worker 后，原始 001/004 的选择、评价时点、任务内设置和首份技术结果一致。它也复核了既有任务配置传递修复：服务不得在任务执行中重新读取当前设置。`rule_set_version` 仍是任务标签；尚无证据表明排队任务跨部署后会按标签加载旧规则正文或依赖清单。因此不能据本探针宣布版本冻结、所有规则或阶段 B 全部验收。

尚未覆盖分族客户样本子任务、升级前缺少逐病例快照的旧任务、真实来源行内容与完整性、真实患者证据、真实模型、调用 Token 与耗时，也没有独立临床金标准。客户样本分族子任务的代码路径已在前述只读清单定位，但需要用其实际创建的子任务单独固定输入验收。跨部署规则版本差异应先取得真实失败序列或受控重放，再决定是否增加版本锁定；不因标签本身存在就新建一套计划框架。

复跑命令（`backend/` 下，纯合成源、无数据库启动和模型调用）：

```powershell
$env:JWT_SECRET='unit-test-secret-only'; $env:DATABASE_URL=''; python -m pytest tests/unit/test_luxian_0609_three_entry_readonly_probe.py tests/unit/test_luxian_0609_task_plan_freeze_probe.py --confcutdir=tests/unit -q --disable-warnings --tb=short
```

初次提交时运行 5 passed、3 warnings，退出码 0；加入下述非空来源回放后运行 6 passed、3 warnings，退出码 0。警告不影响上述固定传参与状态断言；该结论不代替客户样本或临床保护集验收。

## 非空来源补充回放

后续在同一三入口探针加入第二组固定来源行：住院登记入院时间 2026-09-20 08:00，入院记录 ADM-1 完成于当日 09:00；抢救记录 RS-1 写明抢救结束于 2026-09-21 10:00，记录完成于 11:00。来源均为合成行，读取会话继续调用真实快照构造，未连接 PG 或模型。空来源组仍保留，避免只验证正常记录。

三个入口共同的首份病例都发布：001 `compliant/requirement_within_threshold`，耗时 1 小时、剩余 23 小时、证据定位到 `admission_record/ADM-1`；004 同为 `compliant/requirement_within_threshold`，耗时 1 小时、剩余 5 小时、证据定位到 `rescue_record/RS-1`。探针逐字段比较三入口的状态、原因码、客户可见事实、证据和子结论，并断言上述具体时间与文书坐标。它证明相同来源行经过三个路由后确实进入对应规则及发布结果，而不只是空源时恰好同为缺口或不适用；仍不能替代真实病历的临床金标准。

## 任务设置探针的外部取数隔离

同组 `test_luxian_0609_task_plan_freeze_probe.py` 有两项直接调用 bundle 门面，只核对设置读取/正式门禁和非 0609 参数隔离。bundle 输入适配先于这些断言装配证据；原测试未隔离来源表与详情服务回退，数据库不可连接时会在设置边界之前抛连接异常。现仅将这两个外部读取函数固定为空结果，保留真实 bundle 适配、设置读取、门禁及后续被测路径，不改生产行为和预期断言。

使用 `DATABASE_URL=postgresql://test:test@127.0.0.1:1/test`（端口 1 不可连接）与合成 JWT，带 `--confcutdir=tests/unit` 运行上述三入口探针及任务设置探针，结果为 6 passed、3 warnings、退出码 0。该运行证明这些聚焦用例无需真实 PG 连接；不是实际来源读取或数据库集成验收。
