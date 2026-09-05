# LX0609 生产规则扩展边界验收记录

日期：2026-09-05

范围：第三闭环的只读、可复现门禁证据；不新增生产规则，不写数据库，不调用真实模型。

## 已验证调用链

既有 `LX0609-001` 和 `LX0609-006` 的回归从生产 loader 进入：

`load_luxian_0609_dependency_inventory` → `build_luxian_0609_package_plan_from_settings` → `prepare_luxian_0609_execution` → `Luxian0609ExecutionEngine` → `bind_and_reduce_luxian_0609_rule_decisions` → `aggregate_luxian_0609_orchestrated_results` → 生产 customer renderer。

测试仅向 evidence-session provider 注入固定的受控病例行，并以受控假客户端返回 006 的一次严格 JSON 事实提取。它不 patch 规则目录、执行计划、执行器注册、Binding 的来源判断或 renderer。

断言结果：001 的确定性原生判定与 006 的一次受控语义提取共享同一 snapshot、同一 `basic_timeliness` plan batch 和同一 Binding/renderer 链；两条结果均为 `compliant / requirement_within_threshold`。该测试不写入 Canonical 数据库；Canonical 写入仍由既有 `CanonicalResultStore.replace_for_job` 合同测试覆盖。

新增的单选/组合一致性回归分别运行 `001`、`006`、`001+006`。三次的 usage attribution 均为 `basic_timeliness`，且不存在 compatibility batch、legacy wrapper 或 raw native result 回退。组合的两项归一化 Canonical 交付字段分别等于单选结果；001 始终零 LLM 调用，006 单选与组合均为一次、40 输入 token、52 total token，且 prompt 完全一致。客户证据定位也被精确固定：001 为 `admission-001 / admission_record / record_content / 2026-07-15 14:30:00`，006 为 `upper-round-006 / senior_course_record / record_content / 2026-07-16 10:30:02`。

## 076/077 的现状门禁

测试把现有 master 或 phase JSON 复制到临时文件，只增加声明式 `LX0609-076` 和 `LX0609-077`，再替换相应模块的既有 `_MASTER_PATH` / `_SCOPE_PATH` 后调用真实 cached loader（每次均清 cache）。两条 loader 都按预期抛出：

`... must contain ordered rules 001 through 075`

因此 076/077 当前不能进入正式规则加载、计划、prepare、统一引擎、Binding 或 Canonical。本测试记录这个失败门禁，不把它改写为“扩展已通过”。

## 后续待审的最小方向

若业务正式批准扩至 076/077，修改应先限定为声明式目录边界：

1. master 以其声明的有序目录 ID 为唯一权威，移除固定 `001..075` 数量断言；
2. phase scope 只要求与同版本 master 的完整有序集合一致，不再复制固定 75 条常量；
3. contracts、dependency inventory、source 声明和 customer renderer 为新增规则补齐真实元数据及针对性测试。

不新增测试专用 runtime、第二套身份/来源合同或测试专用 executor。新增规则能否进入执行，必须继续由正式目录、计划、来源声明、Binding 和 renderer 的同一条主资料链决定。
