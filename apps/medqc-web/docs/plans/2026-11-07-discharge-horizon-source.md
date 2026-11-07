# 六例已有出院时间的统一终点接入

## 基线与范围

- 基线：`6ad6817b1b66c21b7c94542772a8452215250de5`。
- 分支：`codex/discharge-horizon-source-20261107`，独立工作树，不修改集成分支。
- 既有材料：C16、C17、C18、C19、C20、C22。只复用先前离线取材文件，不再连接业务库或重新抽取PDF。
- 不涉及转科科室、规则阈值、医学状态枚举、模型、迁移或前端。

## 根因与最小修改

这六例登记行的出院时间为空、无首页，但出院文书中已有业务出院时间。
统一受控来源 `inpat_registration.discharge_horizon` 原来只查登记和首页；新任务的文书日期回退也可能遮蔽同日精确时间。
另有显式时区时间与无偏移本地时间混用时，新任务会冻结为冲突。

- `discharge_time.py`：仅负责业务时间来源选择和医院时区归一，不执行医学判定。
- `source_evidence_reader.py`：原受控来源增加出院文书兜底，沿用三坐标、材料schema及文书有效性/PDF去重过滤；过滤在LIMIT前，最多取两行判断不完整。
- `record_repository.py`：查询、显式三坐标和旧ID锚点复用同一选择函数；登记空值不遮蔽同病例入院文书的业务入院时间。没有放宽PDF副本必须使用三坐标的入口保护。
- `evaluation_horizon.py`：新任务冻结前将显式偏移归一至Asia/Shanghai，保留亚秒精度；来源冲突冻结为`time_conflict`，不回落任务日期。
- `evidence_snapshot_provider.py`：承接明确时间冲突；登记入院时间为空时可使用同一会话中已完整取得的入院文书。历史冻结分支不变。
- `source_registry.py`：该受控查询升级为`snapshot-provider-discharge-horizon-v2`。新取材的冻结附带来源及`hospital-discharge-v1`策略标识。

## 来源优先级与冲突合同

1. 已有任务的逐病例冻结终点优先，执行时不拿新取材补齐或替换；旧缺失、冲突和身份不符仍按原合同处理。
2. 新取材：`inpat_registration.discharge_datetime` → `mr.discharge_datetime` → 有效`discharge_record`的业务日期/时间。
3. 高优先级非空时不混用低优先级值，也不以两者的最大/最小时间投票。登记和首页不同值时选择登记；这是明确的权威优先级，不表示已经核实两个值一致。查询路径原先首页优先于登记的不一致已统一。
4. 仅缺表/缺业务时间列、无行或空业务时间才下降优先级；反射或查询失败明确报错，不能装作空来源。
5. 出院文书日期与精确时间同日时使用精确时间；不同日、非空非法值或明确作废的文书候选不作为完整终点，冻结为冲突。不以文书提交、同步、打印时间作为业务出院时间。
6. 所选层级出现多个候选时受控读取标为不完整，不任意挑一行作为完整终点。无时区值沿用医院本地口径，显式偏移按Asia/Shanghai换算后比较。
7. 仅日期来源保留原有日期DTO/冻结兼容合同；本轮不重构其精度语义，也不声称日期可证明精确时效。

## 隔离验证

后端目录执行：

```powershell
python -B scripts/run_pr8_offline_tests.py `
  tests/unit/test_discharge_horizon_document_fallback.py `
  tests/unit/test_qc_workspace_discharge_time_fallback.py `
  tests/unit/test_qc_workspace_discharge_business_time.py `
  tests/unit/test_qc_workspace_admission_business_time.py `
  tests/unit/test_luxian_0609_source_evidence_reader.py `
  tests/unit/test_luxian_0609_frozen_discharge_horizon.py `
  tests/unit/test_luxian_0609_frozen_horizon_entry.py
```

私有回放需显式设置`DISCHARGE_SIX_FIXTURE`为已有材料文件，`DISCHARGE_SIX_OUTPUT`指向忽略的私有目录；缺文件时该入口明确跳过，不联网取材料。
本轮显式提供了既有文件：SHA256 `b69f191a394c3074cbdeae5309825b854244363c2b59df9a8e687ceef5471627`，前后哈希一致。

- 最终定向集合：116通过，0失败，0跳过（11.21秒）；仅有既有Pydantic弃用提示。相关文件Ruff与diff格式检查通过。
- 覆盖来源优先级、缺值回退、查询失败阻断、冲突、重复候选、真实SQLite SQL过滤顺序、时区/亚秒精度及旧冻结入口。
- 原“仅日期”用例原先暗含另一天精确时间；本轮改为真正仅日期输入（`time=None`），不同日冲突由新增用例单独验收，未放宽旧断言。
- 六例分别经过受控终点读取、新任务RecordRepository取材与冻结、Provider、`01-01-01`程序Executor、Binding、Finalizer及Canonical内存SQLite保存读取。
- 六例终点均解析到既有精确出院时间；所选规则均为`compliant/requirement_within_threshold`。保存后的状态、原因、事实、证据摘要及来源引用一致，旧缺失冻结仍未补值。
- 六例只验证一个受影响程序规则及终点链路，不是六份完整质控，更不是27份全量重跑或全部规则覆盖率验收。

## 回退与未验收边界

代码回退到基线即可；无DDL、配置开关或数据清理需求。不得为回退清除历史冻结、结果或材料。
本轮未修改任何已存任务、冻结或结果；不自动修复旧结果，只影响后续新取材/新任务。
未验证PG16/现场账号、真实服务部署及完整病历运行；未调用模型、未写业务库、未推送、未部署。
私有产物仅保留在工作树忽略的`.tmp/0910-full-audit/discharge-horizon-20261107-private/`。
