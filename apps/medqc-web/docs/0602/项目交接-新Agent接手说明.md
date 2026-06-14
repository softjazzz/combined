# 项目交接 - 新 Agent 接手说明

更新时间：2026-06-13

## 1. 当前项目概况

本项目是病案质控系统 `medqc-web`，当前工作目录：

`D:\LLM\LX888\apps\medqc-web`

当前重点不再是单纯 UI 优化，而是让 `泸县0609质控点验证 v1` 这批客户专项规则能够在客户样本验证页面稳定、准确、可解释地跑起来。UI 已经多轮改造，后续 Agent 不要再盲目扩大视觉改动范围，除非用户明确要求。

当前最重要的业务目标：

- `workstation-v4/rules?tab=semantic` 能管理和查看 SC 规则集与泸县0609规则集。
- `workstation-v4/customer-sample-validation` 能选择并运行 `luxian_0609_qc_v1`。
- 泸县0609 49 条客户质控点要能对样本病历输出可信结果。
- 质控执行机制需要解决 pack/fallback/误报/漏报问题，不能只看任务是否跑完。

## 2. 当前优先问题

### 2.1 泸县0609质控分桶策略

目前已做过旁路 POC，不改主干代码：

- 脚本：`D:\LLM\LX888\apps\medqc-web\scripts\qc\poc_luxian_0609_pack_strategy_lab.py`
- 对比过：
  - `baseline_current`
  - `domain_family_max4`
  - `domain_family_max5`
  - `partial_accept_max4`
  - `network_retry_partial_max4`
  - `hybrid_medqc_v1`

已知结论：

- `baseline_current` 在单病历 `visit_id=2313364` 上表现反而更好。
- `hybrid_medqc_v1` 虽然分桶更细，但耗时、token 成本更高，且结论差异较多。
- 首轮人工复核 23 条差异：
  - baseline 更可信：14 条
  - hybrid 更可信：6 条
  - 两者都需要修正：3 条
- 结论：`hybrid_medqc_v1` 暂不应迁入主干。

关键原因不是“规则包越小越准”这么简单，而是当前缺少统一的触发门控。很多规则在没有触发事件时仍交给 LLM 判断，导致误报或不稳定。

### 2.2 baseline 是否有门控

当前 baseline 有一些弱门控，但没有统一可靠的业务触发门控。

已有门控：

- `executor_type`：区分程序规则和 LLM 规则。
- 部分 `ProgrammaticRuleExecutor` 规则有存在性、时间、简单不适用判断。
- 大包 prompt 会形成一定上下文保守性，可能让它在部分规则上比小包更稳定。

缺失门控：

- 手术类规则应先判断是否存在有效本次手术事件。
- 输血类规则应先判断是否存在输血事件、输血医嘱、输血费用或知情同意触发条件。
- 病重/病危/抢救类规则应先判断医嘱或状态是否存在。
- 病理规则应先判断是否存在病理标本、病理报告或手术取材，不能把细菌培养当病理。
- 检查/检验阳性结果类规则应先判断是否存在对应报告和报告时间。

### 2.3 当前最建议的下一步

不要马上改主干 `QCRuleOrchestrator`。

先新增一个旁路 Trigger Gate POC：

- 不写正式任务表。
- 不改正式质控结果。
- 使用 `visit_id=2313364` 先跑。
- 在 LLM 前先对规则做触发门控：
  - 无触发事件：直接返回 `not_applicable`。
  - 数据不足：返回 `data_gap` 或 `uncertain`。
  - 触发存在：再送入 LLM pack。
- 输出与 baseline 的差异，验证是否能减少明显误报。

如果 Trigger Gate POC 明显优于 baseline，再制定迁入主干方案。

## 3. 当前质控规则与数据链路

### 3.1 规则集入口

泸县0609规则集 key：

`luxian_0609_qc_v1`

重要文件：

- `D:\LLM\LX888\apps\medqc-web\backend\app\services\sample_validation_rule_sets.py`
- `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc_rule_sets.py`
- `D:\LLM\LX888\apps\medqc-web\backend\app\data\luxian_0609_rules_v1.json`
- `D:\LLM\LX888\apps\medqc-web\backend\app\services\luxian_0609_rule_catalog.py`

注意：

- `luxian_0609_qc_v1` 是客户专项规则包，不等同于 SC 全量规则。
- 页面展示粒度是 49 条客户质控点，执行时可能映射到底层 59 条左右可执行规则。
- 不要把 `LX0609-xxx` 直接当作底层执行规则 ID 提交给执行器。

### 3.2 当前分桶实现位置

主干分桶执行在：

`D:\LLM\LX888\apps\medqc-web\backend\app\services\qc_rule_orchestrator.py`

已知逻辑：

- `DEFAULT_BUCKET_STRATEGY = "domain_only"`
- `ALLOWED_BUCKET_STRATEGIES = {"domain_only", "domain_family"}`
- 当前规则集里配置的 `fixed_packs` 会被归一化为 `domain_only`。
- 所以 `baseline_current` 的真实含义是：按 `execution_domain + doc_scope` 分桶，再打较大的包。

### 3.3 程序规则位置

程序化规则入口：

`D:\LLM\LX888\apps\medqc-web\backend\app\services\programmatic_rule_executor.py`

这里有部分规则的本地判断，但很多仍然只是关键词或简单存在性，不是完整业务触发门控。

## 4. 旁路 POC 已有产物

最新关键运行结果在：

- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_pack_strategy_20260613-154141.json`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_pack_strategy_20260613-154141.md`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_strategy_effect_compare_20260613-154217.json`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_strategy_effect_compare_20260613-154217.md`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\visit_2313364_documents_snapshot.md`

核心数据：

- baseline_current：
  - 7 个 pack
  - fallback 0
  - 58 条结果
  - 约 100 秒
  - token 约 64658
- hybrid_medqc_v1：
  - 22 个 pack
  - fallback 0
  - 58 条结果
  - 约 134 秒
  - token 约 134834
- baseline 与 hybrid 结论：
  - 相同 35 条
  - 不同 23 条

## 5. visit_id=2313364 人工复核事实

该病历被用于首轮分桶策略对比。

已知事实：

- 有入院记录、初步诊断、日常病程、2 条上级查房、3 条会诊。
- 入院记录 `record_time=2026-03-29 10:05:55`。
- 存在污染时间源：某些结构化诊断时间为 `2026-04-19`，不能拿它替代入院时间。
- 48 小时主治查房存在：
  - 段超主治医师查房 `2026-03-30 09:15:35`
- 72 小时高级职称查房存在：
  - 马晨曦副主任医师查房 `2026-03-31 09:39:27`
- 无有效本次手术：
  - `surgery_record` 是空壳，手术字段、时间、过程为空。
- 无术后首次病程、无抢救、无出院、无输血。
- 会诊记录存在，有“已遵会诊意见”等执行内容；其中一条医生签名为空。
- 影像、肾功能、细菌培养等结果有部分病程/会诊分析。

这个样本说明：如果没有 Trigger Gate，很容易在手术、输血、病理、病重病危规则上误报。

## 6. UI 当前状态和注意事项

### 6.1 工作台整体风格

最近已经把 `workstation-v4` 大量页面调整为 Apple 风格浅色工作台：

- 冷浅灰背景 `#f5f5f7`
- 白色玻璃卡片
- 主蓝 `#0066cc`
- 侧边栏浅色玻璃
- Lucide 图标
- Source Han Sans SC / SF Pro 字体栈

设计 skill 已更新：

`D:\LLM\LX888\apps\medqc-web\.codex\skills\medqc-workstation-design\SKILL.md`

后续改 UI 时必须先读这个 skill。

### 6.2 用户明确说过暂时不用改的区域

智能分析面板暂时不用改。

不要主动重构：

- 右侧智能分析面板
- AI 深度画像面板
- 已经被用户认可的规则页整体外壳

## 7. 当前工作区状态

当前 git 工作区非常脏，有大量已修改和未跟踪文件。

新 Agent 接手后第一件事应该先运行：

```powershell
git status --short
```

注意事项：

- 不要随意回滚文件。
- 不要删除 `.runtime-logs`，除非用户明确要求。
- 不要提交 `dist/`、coverage、临时日志。
- 不要新增 `.vue.ts` mirror 文件。
- 改代码后至少运行：

```powershell
npm run check:encoding
npm run lint
```

如果改前端类型或组件：

```powershell
npm run type-check
```

## 8. 新 Agent 建议执行顺序

### 第一步：读取关键文档

先读下面这些文档，不要直接改代码：

1. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控分桶策略优化方案.md`
2. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609-hybrid-medqc-v1-首轮差异人工复核结论.md`
3. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609-hybrid-medqc-v1-首轮差异复核清单.md`
4. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控集-单病历POC机制梳理.md`
5. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`
6. `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-病历书写规范依据映射表.md`
7. `D:\LLM\LX888\apps\medqc-web\docs\0602\客户第一批质控点-语义规则覆盖矩阵.md`

### 第二步：确认当前脚本

检查：

```powershell
python -m py_compile scripts/qc/poc_luxian_0609_pack_strategy_lab.py
```

必要时只跑 dry-run，不要一上来烧模型调用：

```powershell
python scripts/qc/poc_luxian_0609_pack_strategy_lab.py --visit-id 2313364 --strategies baseline_current,hybrid_medqc_v1 --dry-run
```

### 第三步：实现 Trigger Gate 旁路 POC

建议新增或扩展旁路脚本，不改主干：

`D:\LLM\LX888\apps\medqc-web\scripts\qc\poc_luxian_0609_trigger_gate_lab.py`

或在现有：

`D:\LLM\LX888\apps\medqc-web\scripts\qc\poc_luxian_0609_pack_strategy_lab.py`

中新增 `trigger_gate_baseline` / `trigger_gate_hybrid` 策略。

POC 输出目录：

`D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\`

必须输出：

- 每条规则是否进入 LLM
- 被 gate 拦截的原因
- `not_applicable` / `data_gap` / `pass_to_llm`
- 与 baseline 的差异
- 人工复核建议队列

## 9. 不要做的事

- 不要现在把 `hybrid_medqc_v1` 迁入主干。
- 不要仅凭 “小包理论上更准” 修改生产分桶策略。
- 不要把无触发事件的规则交给 LLM 后再靠 prompt 自己判断不适用。
- 不要用模拟正反例证明真实样本准确。
- 不要把客户样本验证页面跑通当作规则准确率已达标。

## 10. 给新 Agent 的可复制首条指令

可以把下面这段直接发给新对话：

```text
请先阅读 D:\LLM\LX888\apps\medqc-web\docs\0602\项目交接-新Agent接手说明.md。

当前任务不是继续猜分桶策略，而是在不改主干质控流程、不写正式任务表的前提下，实现泸县0609质控集 Trigger Gate 旁路 POC。先用 visit_id=2313364，对手术、输血、病重/病危/抢救、病理、检查检验阳性结果这些规则族做触发门控，输出与 baseline_current 的差异报告。完成后再判断是否值得迁入主干。
```

## 11. 参考说明文档

### 业务与规则

- `D:\LLM\LX888\apps\medqc-web\docs\0602\质控点及规则.xlsx`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\医疗机构病历书写规范（2026年版）_合并.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\客户第一批质控点-语义规则覆盖矩阵.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-病历书写规范依据映射表.md`

### 上线与验证

- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点正式上线长程任务.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点正式上线目标-完成情况.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-上线准备度看板.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-正式版发布闸门报告.md`

### 分桶与 POC

- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控分桶策略优化方案.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控集-单病历POC机制梳理.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609-hybrid-medqc-v1-首轮差异复核清单.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609-hybrid-medqc-v1-首轮差异人工复核结论.md`
- `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_hybrid_medqc_v1_first_diff_review.csv`

### 运行日志

- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_pack_strategy_20260613-154141.md`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_pack_strategy_20260613-154141.json`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_strategy_effect_compare_20260613-154217.md`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\luxian_0609_strategy_effect_compare_20260613-154217.json`
- `D:\LLM\LX888\apps\medqc-web\.runtime-logs\qc-pack-poc\visit_2313364_documents_snapshot.md`

### UI 设计规范

- `D:\LLM\LX888\apps\medqc-web\.codex\skills\medqc-workstation-design\SKILL.md`
- `D:\LLM\LX888\apps\medqc-web\docs\gap\WorkstationV4-医疗浅色-DESIGN.md`

## 12. 当前交接结论

当前最关键问题不是“有没有 49 条规则”，而是：

1. 规则执行前缺少统一触发门控。
2. 当前分桶策略对准确率影响不是单调的，小包不一定更准。
3. baseline 在 visit_id=2313364 上更可信，但它不是准确率基线，只是当前生产吞吐基线。
4. 下一步应该用旁路 Trigger Gate POC 找到可迁入主干的可靠策略。
