# 正式质控结构化证据 84 条 POC Gothrough

本文档用于配合 `/goal` 长任务执行。`/goal` prompt 只写短目标，执行细节以本文档为准。CLI 在每个阶段开始前都应先回看本文档，避免把 POC 做成正式链路替换、把弱关键词当强证据、或遗漏 Sheet2 回归门禁。

## 一句话目标

把当前 5 条规则的“小模型结构化证据抽取 + 大模型裁决”POC，扩展为覆盖正式 `sc_content_full_v1` / `final fast_screen_full` 的 84 条内涵质控规则的只读旁路 POC，并输出可比较的稳定性、token、耗时和质量报告。

## 当前基线

- 当前正式 84 条主链路：`fast_screen_full` + fixed packs + 二审裁决 + 后处理分流。
- 当前 POC 脚本：`apps/medqc-web/backend/scripts/run_formal_qc_structured_evidence_poc.py`。
- POC v3 已覆盖 5 条规则：`SC-036`、`SC-070`、`SC-099`、`SC-100`、`SC-101`。
- POC v3 10 病历结果：
  - provider_error=0
  - timeout=0
  - extractor_parse_error=1
  - adjudicator_parse_error=0
  - absent_trigger_data_gap_count=0
  - SC-036/SC-101 rejected_without_supporting_quote_count=0
  - 决策分布：`rejected_by_system=31 / data_quality_gap=19 / confirmed_defect=0`
  - v3 tokens=168862，正式 84 条 baseline tokens=608247；注意这不是等价覆盖，只能说明 5 条 POC 的输入方式有明显 token 优化空间。
- Sheet2 回归必须保持：`exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0`。

## 不可改变的边界

1. 这是只读 POC，不替换正式 84 条线上质控主链路。
2. 不改 Sheet2 客户样本验证验收结论。
3. 不把 `qc_review_candidate` 或“待人工复核”作为终态目标；正式终态只允许：
   - `confirmed_defect`
   - `data_quality_gap`
   - `rejected_by_system`
   - `technical_error_internal`
4. 不允许把关键词词表当成强触发证据。关键词只能作为 weak hint。
5. 强触发必须来自结构化表、明确文书字段，或清晰的事件句，例如“动作 + 对象 + 时间/数量/部位/结果”。
6. 不硬编码客户样本里的具体姓名、疾病、检查结果、日期、病区或人工问题文本。
7. 不提交密钥，不改 `.env`，阿里云 key 只允许通过临时环境变量使用。
8. 当前 `.git` ACL 可能禁止 `git add` 创建 `.git/index.lock`；如果仍失败，不要反复折腾 git，保留文件清单和验证结果即可。

## 84 条扩展的正确做法

不要把 84 条规则逐条写成 84 个 LLM 调用。应先按证据域分族，每个证据域生成结构化 evidence package，再让裁决模型针对该 evidence package 中的相关规则输出判定。

推荐证据域：

1. 入院记录结构与主诉现病史域
2. 首次病程与诊断依据域
3. 病程记录连续性与病情变化域
4. 检查检验异常与处理意见域
5. 会诊意见与落实域
6. 医嘱、执行、费用或治疗闭环域
7. 手术、术前讨论、术后首次病程域
8. 植入物、高值耗材、病理取材域
9. 出院记录、出院诊断、出院医嘱域
10. 输血、危急值、特殊记录域

每个 evidence package 至少包含：

- `visit_id`
- `evidence_family`
- `trigger.status`: `present | absent | unknown`
- `trigger.reason`
- `trigger.quotes`
- `required_evidence[]`
- `supporting_evidence[]`
- `contradicting_evidence[]`
- `missing_evidence[]`
- `coverage_flags[]`
- `data_quality_flags[]`
- `source_quote_quality`: `strong | weak | missing`
- `trigger_strength`: `strong | weak | absent | unknown`

每条规则的裁决至少包含：

- `rule_id`
- `decision`
- `reason`
- `supporting_quote`
- `supporting_quote_ids`
- `missing_slots`
- `confidence`
- `coverage_flags`
- `gate_supporting_quote`，当系统依据“已有证据所以驳回”时必须有引用。

## 阶段拆解

### 阶段 1：盘点 84 条规则和证据域映射

目标：生成 84 条规则 inventory，不调用 LLM。

要求：

- 从现有正式规则集、fixed pack、`sc_content_full_v1` 配置或代码中提取规则，不手工拍脑袋列 84 条。
- 每条规则输出：
  - `rule_id`
  - `rule_name`
  - `formal_pack`
  - `current_document_scope`
  - `suggested_evidence_family`
  - `trigger_type`
  - `required_sources`
  - `structured_support_level`: `ready | partial | unsupported`
  - `reason`
- 输出文件：
  - `apps/medqc-web/docs/0508/formal_qc_structured_evidence_poc_84_rule_inventory.csv`
  - `apps/medqc-web/docs/0508/formal_qc_structured_evidence_poc_84_rule_inventory.json`

门禁：

- inventory 中正式规则数必须等于 84。
- 每条规则必须有 evidence family。
- `unsupported` 允许存在，但必须写明原因，不能静默跳过。

### 阶段 2：抽取器按证据域重构，不按规则重构

目标：扩展 `run_formal_qc_structured_evidence_poc.py`，让它按证据域生成 packages。

要求：

- 保留 v1/v2/v3 产物，不覆盖。
- 新增 84 规则模式参数，例如 `--scope all84`。
- 复用现有 bundle/document assembly，不直接伪造 evidence。
- 抽取器输出 JSON 必须可解析；失败要有 retry 和 parse error 统计。
- 不允许一条规则一个 extractor call。

建议输出：

- `formal_qc_structured_evidence_poc_84_summary.csv/json`
- `formal_qc_structured_evidence_poc_84_issue_review.csv/json`
- `正式质控结构化证据84条POC阶段报告.md`

### 阶段 3：二审裁决按 evidence family 批量裁决

目标：每个 evidence package 对相关规则批量裁决。

要求：

- 大模型仍使用阿里云 `qwen3.6-35b-a3b`。
- 小模型抽取器使用阿里云 `qwen3.5-35b-a3b`。
- 不输出“待质控员确认”。
- `confirmed_defect` 必须满足：
  - trigger strong 或规则本身不需要 trigger；
  - required evidence 缺失或 contradicton 清楚；
  - 有可读 `supporting_quote`；
  - 不是仅凭记录时间、标题、模板语或“未见/缺失”总结。
- `rejected_by_system` 分两类：
  - trigger absent / 规则不适用：可以没有 quote，但必须有明确 trigger reason。
  - 已有证据所以驳回：必须有 `supporting_quote` 或 `gate_supporting_quote`。
- `data_quality_gap` 用于源表、本地 CDM、bundle 或跨表证据不足，不包装成缺陷。

### 阶段 4：10 病历只读回放

目标：用与前序阿里云 10 病历一致的样本做对照，不扩大样本。

建议样本沿用既有正式质控 10 病历集合，避免换样本导致不可比较。

必须统计：

- visit_count
- rule_count
- evidence_family_count
- extractor_call_count
- adjudicator_call_count
- provider_error
- upstream_http_error
- timeout
- rate_limit
- extractor_parse_error
- adjudicator_parse_error
- total_tokens
- wall_clock_time
- display_status counts
- confirmed_without_quote_count
- rejected_existing_evidence_without_quote_count
- absent_trigger_data_gap_count
- weak_trigger_confirmed_count

建议门槛：

- provider/upstream/timeout/rate_limit=0。
- parse error 允许极少量，但必须有 retry 和 fallback 记录。
- `confirmed_without_quote_count=0`。
- `weak_trigger_confirmed_count=0`。
- `absent_trigger_data_gap_count=0`。
- 同 84 条正式 baseline 对比，token 至少下降 40%，否则结构化抽取没有效率价值。
- 平均墙钟耗时不应显著高于正式 84 条当前阿里云链路；若变慢，报告必须解释瓶颈是 extractor 次数、串行执行还是模型响应。

### 阶段 5：质量复核报告

目标：不要只看数量，要判断“少报/误驳回/数据缺口”的性质。

报告必须回答：

1. 结构化证据 POC 对 84 条是否技术可行？
2. token 是否真的下降？下降比例是多少？比较口径是否等价？
3. 耗时是否可接受？慢在哪里？
4. confirmed_defect 是否有足够 quote？
5. rejected_by_system 是否存在疑似误驳回？
6. data_quality_gap 是同步/bundle 问题，还是证据 schema 未覆盖？
7. 哪些规则可以下一步进入 feature flag 旁路？
8. 哪些规则仍不适合结构化证据方案？

## 禁止事项

- 禁止为了让指标好看而把不确定结果全打成 `rejected_by_system`。
- 禁止把 `data_quality_gap` 当成质控缺陷。
- 禁止以“客户样本人工问题”为规则触发源。
- 禁止扩大到 20/50 病历，除非 10 病历门禁先通过。
- 禁止改正式页面展示、正式落库、正式任务 API。
- 禁止提交 provider probe、客户机导出、数据库审计临时文件。

## 推荐提交范围

如果 `.git` ACL 修复后需要提交，只允许显式添加以下类型文件：

- `apps/medqc-web/backend/scripts/run_formal_qc_structured_evidence_poc.py`
- `apps/medqc-web/docs/0508/formal_qc_structured_evidence_poc_84_*.csv`
- `apps/medqc-web/docs/0508/formal_qc_structured_evidence_poc_84_*.json`
- `apps/medqc-web/docs/0508/正式质控结构化证据84条POC阶段报告.md`
- 必要的单测文件，若本轮新增了可重复测试。

不要执行 `git add .`。

建议 commit message：

```text
扩展正式质控结构化证据84条POC
```

## 必跑验证

在 `apps/medqc-web` 下：

```powershell
npm run check:encoding
npm run lint
npm run test:sheet2-exact-review:regression
```

如果改了前端或共享类型，额外跑：

```powershell
npm run type-check
npm run test:unit
```

后端脚本至少跑：

```powershell
python -m py_compile apps/medqc-web/backend/scripts/run_formal_qc_structured_evidence_poc.py
python apps/medqc-web/backend/scripts/run_formal_qc_structured_evidence_poc.py --self-test
```

Sheet2 回归最终必须保持：

```text
exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0
```

## `/goal` 短 prompt

可以把下面这段作为 `/goal` 内容：

```text
目标：根据 apps/medqc-web/docs/0508/2026-05-14-正式质控结构化证据84条POC-gothrough.md，把正式 sc_content_full_v1 / final fast_screen_full 的 84 条内涵质控规则扩展为只读结构化证据 POC。不要替换正式质控主链路，不改页面/正式落库/Sheet2 验收结论。先生成 84 条规则 inventory，再按证据域生成 evidence package，用 qwen3.5-35b-a3b 做结构化抽取、qwen3.6-35b-a3b 做裁决，保持四类终态：confirmed_defect/data_quality_gap/rejected_by_system/technical_error_internal。严禁把关键词当强触发，weak trigger 不得 confirmed，absent trigger 不得 data_gap；已有证据所以驳回时必须带 quote。只跑既有 10 病历只读回放，不扩大样本。输出 84 inventory、summary、issue_review 和阶段报告。验证 py_compile、self-test、check:encoding、lint、Sheet2 regression，Sheet2 必须保持 156/102/25/0。当前 git ACL 可能无法提交；如无法 git add，不要反复折腾，保留文件清单和验证结果。
```

