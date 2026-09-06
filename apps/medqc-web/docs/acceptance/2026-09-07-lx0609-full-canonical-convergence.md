# LX0609 旧规则族统一 Canonical 主链最终验收

## 验收结论

本轮批准范围已完成：LX0609 原有 `001–075` 规则族的结果交付职责已从核心
聚合器迁出，正式已裁决结果统一沿
`RuleDecision → ReducedRuleDecision → Finalizer → 公共证据投影 → Canonical Result`
交付。核心聚合器只保留输入索引、wrapper 顺序装配和 Canonical 状态统计，不再按
规则号解释业务状态、校验规则专属事实或选择规则专属证据。

当前规则总表已经扩展为 `001–077`，其中 `076/077` 的真实生产扩展证明继续成立；
原有六条待口径发布规则 `025/028/049/056/059/075` 仍按原策略输出
`not_executed`，客户运行范围排除的 `033/034/035/041/042` 也未改变。本次结构迁移
没有借机修改上述业务策略。

完成度按本任务批准口径计为 **100%**：八个规则族均已完成执行器事实所有权、
Binding 校验、公共证据投影和 Canonical 交付边界收口；聚合器规则专属业务分支为
零。这里的 100% 不表示所有暂停规则已经发布，也不表示历史兼容入口被删除。

## 最终职责边界

- 规则执行器：负责适用性、状态、原因码、关键事实和 `fact_refs`。
- Binding / Reducer：验证引用、同源性和结构化判定合同。
- Finalizer：校验客户事实合同，调用声明式 Renderer 和公共证据投影，并生成
  Canonical 结果；非法合同保持 `technical_error`。
- Renderer：只组织客户文案，不重新计算业务状态。
- Aggregator：只建立输入索引、按 wrapper 顺序装配和统计 Canonical 状态。
- Store / API / 前端：搬运或展示 Canonical 结果，不按规则号重新判定。
- `luxian_0609_legacy_result_adapter.py`：隔离旧 direct/native/mapped/gate 交付合同，
  仅供显式旧入口、关闭统一引擎或未产生 ReducedDecision 的兼容场景使用；正式 active
  规则主链不会自动回退至该适配器。

## 结构结果

- `luxian_0609_result_aggregator.py` 从历史约 6,618 行收口到当前 185 个物理行
  （包含文件末尾空行）。
- 隔离后的 `luxian_0609_legacy_result_adapter.py` 当前 673 个物理行；它承载完整旧
  交付兼容职责，不是逐函数转发壳，也不参与正式 ReducedDecision 分支。
- 聚合器中的 `LX0609-xxx` 直接引用：0。
- 聚合器中的规则专属事实校验、状态解释和证据生成：0。
- 批量 worker 的会诊证据二次拼装：0。
- Canonical Store 的规则号专属状态/事实重判：0。
- 当前 Canonical 结果读取侧不再重写已保存的客户结论；旧或非法正式结果以
  `technical_error/canonical_result_envelope_invalid` 失败关闭，不伪装为临床
  `data_gap` 或 `uncertain`。
- 旧纯文本 `/api/v1/qc/sichuan/test-rule` 不再执行 LX0609，返回受控 422；正式
  单规则、批量和客户样本验证继续使用结构化主链。

## 行为与失败语义

迁移保持以下批准边界：

- 合同不匹配、执行器异常、超时、非法结构：`technical_error`。
- 已接入数据源缺少必要资料：`data_gap`。
- 事实存在但语义无法可靠判断：`uncertain`。
- 触发事件不存在或观察窗口尚未成熟：按已批准规则口径进入
  `not_applicable`。

结构迁移与业务缺陷修复分开提交；客户证据按坐标集合比较，数组顺序不作为优先级
或行为变化依据。迁移未新增引擎、fallback、状态机、全局注册中心、数据库字段、
API DTO 或前端状态解释。

## 验收证据

### 全量 LX0609 回归

执行范围：

- `backend/tests/unit/test_luxian_0609*.py`
- `backend/tests/integration/*luxian_0609*.py`
- `backend/tests/unit/test_qc_sichuan_test_rule.py`

结果：**4,948 passed，38 warnings，190.90 秒**。警告均为现有 FastAPI、Starlette、
Pydantic 和 SQLAlchemy 弃用提示，不是本次失败。

### 聚焦和三入口回归

- Aggregator、Finalizer、Canonical delivery 聚焦回归：452 通过。
- 读取侧边界、Canonical delivery 与显式复核服务：125 通过。
- 历史失败清单复核：409 通过。
- 规则族聚焦及正式主链组合回归：536 通过。
- 原 `001–075` 正式三入口验证：2 通过。
- `030/032` 单规则、批量、客户样本验证回归：6 通过。
- `076/077` 真实生产规则扩展入口测试包含在本次全量回归内，并保持无需修改
  聚合器、保存、API DTO 或前端解释。

### 静态架构守卫

- CodeGraph 已同步当前 33 个变更文件，并确认正式调用路径为
  `aggregate_luxian_0609_results → finalize_luxian_0609_reduced_customer_result`。
- `rg "LX0609-[0-9]{3}" luxian_0609_result_aggregator.py` 无命中。
- 批量 worker 中 `_consultation_evidence_items_for_batch` 无命中。
- Store 中规则号、`surgery_document_targets`、`historical_evidence_missing` 和聚合器
  依赖均无命中。
- `git diff --check` 通过。

## 保留边界与后续规则

显式复核服务仍可生成不自动回写 Canonical 的 `review_report`；这是人工复核功能，
不是结果主链的第二所有者。旧兼容适配器也暂时保留公开导入兼容，但已与正式 active
规则主链隔离。

后续新增或修改普通质控规则必须继续遵守：规则声明和所属执行器产生
`RuleDecision + fact_refs`，公共 Binding/证据投影生成 Canonical 结果；不得向核心
聚合器、Store、保存接口、API DTO 或前端增加规则专属业务判断。若某个显式旧入口
确需退役，应另立最小任务，不与新规则业务开发混做。
