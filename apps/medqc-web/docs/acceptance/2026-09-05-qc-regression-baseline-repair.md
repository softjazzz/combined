# LX0609 既有回归失败关闭记录

## 结论

阶段 A 已关闭原有 5 个失败点。最终完整运行 `backend/tests/unit/test_luxian_0609_*.py`，共 `4278 passed in 34.19s`，未使用 `-k not`、`--deselect`、skip 或 xfail。

本轮包含两类处理：4 个失败属于冻结测试仍依赖旧实现细节，生产合同无需修改；1 个失败属于 LX0609-070 的真实证据选择缺陷，已在执行器首次缺失位置和来源读取合同处修复。技术错误状态、规则目录范围、API DTO、数据库 schema 和前端解释逻辑均未改变。

## 测试隔离协议

- 全局单元测试夹具过去会在每个用例前清理 `qc.sync_trigger_idempotency` 持久表，存在误触本机数据库的风险。
- 已新增仅清理进程内幂等状态的测试入口，并将全局夹具改为只调用该入口；完整持久化清理函数的生产语义保持不变。
- 纯逻辑聚焦回归将 `DATABASE_URL` 和 `REMOTE_DB_URL` 指向不可连接的隔离地址。
- 全量 LX0609 回归中，少数历史“单元测试”需要读取本机派生病例基线。该组使用 PostgreSQL `default_transaction_read_only=on`，任何写语句都会由数据库拒绝。
- 隔离修复提交：`9ecb8be1c`。

## 原始失败逐项结论

### 1-3. 病危/病重医嘱三种有效状态的 row_ref

位置：`test_severity_order_reader_accepts_only_audited_effective_statuses_without_echo` 的“新开”“执行中”“停止”三个参数。

- 复现：旧断言按早期字段集合手工重算固定摘要，当前实现已将 `planned_start_datetime`、`planned_end_datetime` 和标准化生命周期状态纳入受控来源身份。
- 根因：测试冻结了序列化实现细节，未冻结客户安全输出与来源定位不变量；生产读取结果正确。
- 业务影响：无生产资料丢失。若把旧摘要恢复到生产代码，反而会忽略病危区间结束时间变化。
- 修改：只更新 `test_luxian_0609_evidence_snapshot_provider.py`。现在断言有效状态、生命周期、计划起止时间、敏感原字段不外泄、同输入稳定、关键时间变化会改变引用。
- 提交：`fa4a11ce2`。

### 4. LX0609-059 来源注册版本断言

位置：`test_059_binds_only_event_order_and_course_decision_support_sources`。

- 复现：测试把全局来源注册版本固定为 v23；当时生产注册表已合法升级，059 自身所需来源集合未变化。
- 根因：测试把无关规则引起的全局注册版本升级误当成 059 业务合同。
- 业务影响：无生产缺陷；删除所有版本门禁也不合适。
- 修改：只更新 `test_luxian_0609_evidence_snapshot.py`。现在验证快照、身份字典与规范序列化都携带当前唯一注册版本，同时继续严格断言 059 的来源集合和合同一致。
- 提交：`fa4a11ce2`。

### 5. LX0609-070 多次输血证据链

位置：`test_070_multi_transfusion_preserves_canonical_decision_facts_and_evidence`。

- 复现：规则状态和九项检查事实正确，但 Canonical 客户证据只有入院登记，缺少输血记录和参与判定的检验报告。
- 首次丢失位置：`native_extended_document_execution` 只将三个来源级快照引用写入 `RuleDecision.fact_refs`，没有选择实际消费的逐行文书引用。Binding 原样保留输入，并非丢失层。
- 次要来源缺陷：`mr_bloodtrans` 的受控字段白名单遗漏 CDM 已有的 `document_id`，真实主链无法形成输血文书业务坐标。
- 旧回退为何不能保留：聚合器的来源级回退只会猜单行来源；多次输血和同报告多检验行都会被跳过。放松同源或唯一性校验会产生错位证据。
- 修复：
  - 070 执行器只选择它实际消费的可用住院登记、全部输血事件和命中输血前九项的检验行；普通检验不进入逐行引用。
  - 公共证据投影允许同一来源的多个不同文书；同一业务文书拆成多行时，只有全部材料行均被执行器选择才折叠为一个坐标，部分选择继续拒绝。
  - 明确无输血触发事件时不展示住院或检验文书证据。
  - `mr_bloodtrans` 增加 `document_id`，来源注册升级为 v25，输血查询合同升级为 v2，防止旧快照与新身份合同混用。
- 修改文件：`customer_evidence_enrichment.py`、`native_extended_document_execution.py`、`native_transfusion_execution.py`、`source_evidence_reader.py`、`source_registry.py` 及对应单元测试。
- 提交：`8fc1c10ba`。

## 验证结果

### 聚焦回归

- 070 执行、输血判定、来源读取和公共文书投影：`433 passed in 2.25s`。
- 新增覆盖：两次输血、一个来源下两个检验报告、同报告多材料行、无关普通检验排除、同 ID 部分选择拒绝、无输血触发不展示证据。
- 生产及本轮其余测试文件 Ruff 通过。`source_evidence_reader.py` 在本轮前已有两个重复字典键告警，本次只增加一个 CDM 字段，未把历史 lint 清理混入证据修复。

### 完整 LX0609 回归

- 收集：4278 项。
- 结果：`4278 passed in 34.19s`。
- 目录仍使用当前批准的 75 条生产规则；070 仍走既有 native extended-document 执行器；无 LLM 调用、Token 或 Prompt 变化。

## 剩余风险

- 070 的多文书证据闭环目前以受控合成材料验证；若客户源库的 `mr_bloodtrans.document_id` 实际长期为空，状态和事实仍可判定，但客户证据无法生成精确输血文书坐标。需要在后续真实样本验收中记录源字段覆盖率，不能用猜测 ID 回退。
- 本记录只关闭阶段 A，不代表会诊规则族的聚合器业务所有权已经退出，也不代表可以开始批量新增 20～30 条规则。
