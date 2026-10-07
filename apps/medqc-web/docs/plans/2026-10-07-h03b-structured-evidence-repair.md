# H-03b：术前讨论结构化内容证据修复

日期：2026-10-07。核对基线：6fbee7ed22f948cd640e31aa955db68c408998c1。本轮未提交。

## 复现与原因

专属单元测试最初 6 失败、2 通过。术前讨论 record_content 为空、host_summary 有实际内容时，证据补齐却返回 document_title；没有标题时无摘录。原因是通用摘录候选不包含讨论结构化内容。另查明 latest 读取原文时只有合成模板章节，不能按 host_summary 定位，会覆盖原字段摘录。

候选原因检查：结构化字段漏读已确认；冻结材料缺字段被四例真实来源回放排除；保存/API 是否丢字段通过实际隔离保存与读取核对。

## 最小修改

- customer_evidence_enrichment.py：仅 presurg_discussion 按 record_content、content、host_summary、discuss_staff 查找实际字符串内容，保留准确 field_path。标题不充当内容；空内容仅保留文书引用。沿用空白压缩、300字符和省略号规则。
- document_assembly/assembler.py：讨论文书提供真实字段章节与 source_field，不再把合成模板当作实际字段。assembled_text 原有生成逻辑不变，其他文书不变。
- custom_qc_workspace_service.py：仅讨论文书的显式字段无法唯一定位时，不回退另一个字段或模板来覆盖其摘录。

不改临床状态、事实、缺项、判据、Prompt 或发布范围。摘录表示该字段实际写了什么，是原文核查入口；不声称一段300字符摘录能够单独证明整份文书缺少某项。只有 v2_schema.discuss_suggestion 的情况不输出伪造的顶层路径：本轮未扩展现有单段 field_path 公共合同。

## 实际验证

- 新单元测试修复后 8/8 通过；覆盖标题、正文、结构化小结、参与人员、非字符串/非法嵌套、重复文书ID、组装与授权字段回读、缺字段和重复章节不得回退。
- 合成三种状态（合规、不合规、抽取失败资料不足），通过真实执行器、归约和 Finalizer 生成非空证据；再在三业务入口实际保存 SQLite，通过批详情和 latest API 回读。3/3 通过，未清空证据绕过保存边界。
- 四例真实已保存响应离线重放：使用独立 PG 只读事务，并读回 transaction_read_only=on；每例仅 Replay 返回旧响应且严格检查送模输入完全相同，没有模型调用。C02 不合规、C09 合规、C04 资料不足、C10 合规，均获得 host_summary 的内容摘录。C04 失败引文不进入公开结果。
- 将四例 Finalizer 输出连同真实来源字段送入上述隔离链路，三入口 SQLite 实际保存、批详情及 latest API 比对，4/4 通过。此处正式医院读取由固定来源替身替代，不是客户 PG 运行任务。
- 与原保存的 C02/C09/C04 Finalizer 回放对照，除 evidence/customer_evidence 外所有字段相同；旧对照文件没有 C10，不声称完成该例完整旧结果对照。
- 相关6文件 470通过；现有单病历授权摘录2通过。Ruff 对3生产文件及2测试文件全部通过；git diff --check通过。

最初回归命令有一处旧测试文件名不存在，收集0项；更正后为上述470及2项。最初真实链路测试错误地将压缩/截断后的摘录与原始完整空白文本比较，4项失败；改为与Finalizer产物比较，另由回放脚本独立验证摘录确属该来源字段，随后4项通过。没有修改病例预期。

## 复现命令与私有材料

在 apps/medqc-web 目录：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_discussion_evidence_content.py -q
python -m pytest backend/tests/integration/test_luxian_0609_discussion_evidence_roundtrip.py -q
python .tmp/h03b-repair-private/replay.py
python -m pytest .tmp/h03b-repair-private/test_real_roundtrip_private.py -q
```

私有回放、原始来源、结果及日志位于 `.tmp/h03b-repair-private/`，不提交。没有改动 Claude 私有脚本或响应。

## 范围与未覆盖

不新增模型调用、不写PG、不重启、不推送、未暂存或提交。没有浏览器精确高亮验收、临床充分性验收、模型稳定性验收。未修 H-02 的引文失败本身；C04 仍为资料不足。未扩展所有术前讨论字段的证据集合，文书仍一个精确引用与一个有内容的字段摘录。父代理与 Claude 应独立判断此具体缺陷可否关闭，不把本轮称为整条规则验收完成。

## 父复审补充修复

父复审确认两处边界问题，本轮已先补红灯用例（2失败、8通过）再修复：

1. 精确字段章节只能来自真实字符串。dict/list/数值不再经 str 转为 repr；enrich→assemble→授权摘录整链核验，无 field_path 时也不能把 JSON 对象或元数据当内容摘录。
2. v2_schema/旧 JSON 中已有正文不能因只生成顶层时间章节而从阅读界面消失。保留旧 assembled_text 逻辑；其内容未被真实字符串章节涵盖时，补展示专用 presurg_discussion_template 章节。此合成章节不登记为精确来源字段，讨论授权摘录明确拒绝该章节（包括直接传模板 field_path），也不回退时间或合成正文作为证据。

新增测试保留“v2_schema.host_summary + 顶层 record_time”的原反例，断言旧正文仍在 sections 可见，同时没有伪造 host_summary/模板证据。此次没有扩大嵌套字段的公共定位合同。

最终：专属10项全部通过；连同术前执行、聚合、文书、授权读取及三状态三入口保存/API回归共477项通过；四例真实响应隔离三入口保存/latest/批API再跑4项通过。Ruff与git diff --check通过。父复审日志在私有目录 parent-review-\*。本子任务仍未暂存或提交。

## 主协调提交验收

独立复跑最终新增反例与三状态执行、SQLite保存、API读取：13项通过。三份生产文件与两份测试Ruff及diff检查通过。此前编码、ESLint、类型检查已执行；前端全量单测因本机缺少`@jridgewell/gen-mapping`无法启动，不计通过。没有追加真实模型调用、写客户PG或重启服务。
