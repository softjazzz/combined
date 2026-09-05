# LX0609 生产规则扩展边界验收记录

日期：2026-09-05

范围：记录生产目录扩展边界的历史验证与当前状态；不新增生产规则，不写数据库，不调用
真实模型。

> 2026-09-05 勘误：本文件早期版本记录了 master 与 phase 固定 75 条的阻断。当前代码已
> 由 master 按声明数量校验连续规则 ID，phase 只校验与同版本 master 完全一致。原阻断
> 已修复，下面以当前实现为准。

## 已验证调用链

既有 `LX0609-001` 和 `LX0609-006` 的回归从生产 loader 进入：

`load_luxian_0609_dependency_inventory` → `build_luxian_0609_package_plan_from_settings` → `prepare_luxian_0609_execution` → `Luxian0609ExecutionEngine` → `bind_and_reduce_luxian_0609_rule_decisions` → `aggregate_luxian_0609_orchestrated_results` → 生产 customer renderer。

测试仅向 evidence-session provider 注入固定的受控病例行，并以受控假客户端返回 006 的一次严格 JSON 事实提取。它不 patch 规则目录、执行计划、执行器注册、Binding 的来源判断或 renderer。

断言结果：001 的确定性原生判定与 006 的一次受控语义提取共享同一 snapshot、同一 `basic_timeliness` plan batch 和同一 Binding/renderer 链；两条结果均为 `compliant / requirement_within_threshold`。该测试不写入 Canonical 数据库；Canonical 写入仍由既有 `CanonicalResultStore.replace_for_job` 合同测试覆盖。

新增的单选/组合一致性回归分别运行 `001`、`006`、`001+006`。三次的 usage attribution 均为 `basic_timeliness`，且不存在 compatibility batch、legacy wrapper 或 raw native result 回退。组合的两项归一化 Canonical 交付字段分别等于单选结果；001 始终零 LLM 调用，006 单选与组合均为一次、40 输入 token、52 total token，且 prompt 完全一致。客户证据定位也被精确固定：001 为 `admission-001 / admission_record / record_content / 2026-07-15 14:30:00`，006 为 `upper-round-006 / senior_course_record / record_content / 2026-07-16 10:30:02`。

## 076/077 的当前目录边界

当前测试把 master 与 phase JSON 复制到临时文件，连续追加声明式 `LX0609-076` 和
`LX0609-077`，再通过真实 cached loader 加载。master 接受连续扩展，phase 在与 master
完整有序集合一致时也接受扩展。目录层不再存在固定 75 条阻断。

这只证明目录能够扩容。真实新规则仍必须补齐业务定义、规则合同、来源声明、所属执行器、
声明式客户文案和针对性测试；缺少任一项时，正式计划必须失败关闭，不能凭目录条目直接
上线。

## 后续真实规则验收

业务正式批准新规则后，应选择一条 native 与一条受控语义规则，沿正式目录、计划、来源
声明、执行器、Binding、公共证据投影和 Canonical 主链完成三业务入口验证。新增规则不应
要求修改聚合器、任务公共入口、保存合同、API DTO 或前端状态解释；如果需要，应先定位
重复业务所有者并单独治理。
