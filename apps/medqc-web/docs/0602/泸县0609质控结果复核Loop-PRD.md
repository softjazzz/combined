# 泸县0609质控结果复核 Loop PRD

## Problem Statement

LX0609 质控任务已经能运行并展示结果，但客户演示和试点过程中仍会出现“结果需要二次判断”的情况，例如：

- 没有会诊申请、会诊记录等强证据，却进入会诊类 `uncertain`。
- `data_gap` 被客户误解成正式缺陷。
- 质控结论与状态矛盾，例如文本说“已记录/未超时”，状态却是 `non_compliant`。
- 关键证据太短、来源不清，或包含内部技术话术。
- 多病历任务中，客户难以快速判断哪些结果可信、哪些需要人工复核。

用户需要一个可控的“结果复核 loop”，在不改写原始质控结果的前提下，自动生成复核建议，帮助实施人员和客户判断哪些结果可以展示，哪些需要人工复核。

## Solution

新增 **LX0609 结果复核 loop**。

用户在质控任务完成后，手动点击 `复核本次结果`。系统先执行规则化 verifier，再对风险项调用 LLM verifier，生成复核报告。复核报告保存到任务 `summary.review_report`，不直接修改原始质控结果。

前端在任务中心和结果抽屉中展示复核摘要和复核详情；HTML 明细导出中同步包含复核报告。

## User Stories

1. As an 实施人员, I want 在质控任务完成后点击 `复核本次结果`, so that 我可以快速发现疑似误判。
2. As an 实施人员, I want 看到复核报告中的高、中、低风险分类, so that 我可以判断哪些问题需要优先处理。
3. As an 质控员, I want 知道某条 `data_gap` 是数据不足而不是正式缺陷, so that 我不会误判病历质量。
4. As an 质控员, I want 看到复核建议状态和原因, so that 我可以决定是否人工复核。
5. As an 演示人员, I want 避免客户看到 `LLM`、`raw_response`、`证据模板`、`映射执行规则` 等内部话术, so that 客户看到的是业务化表达。
6. As an 演示人员, I want 在任务中心直接看到复核摘要, so that 我不必打开完整结果也能掌握风险。
7. As an 客户, I want 知道“这条结果为什么需要人工复核”, so that 我能理解数据不足和正式缺陷的区别。
8. As an 开发人员, I want 规则化 verifier 先筛风险项, so that LLM 调用成本和不稳定性可控。
9. As an 开发人员, I want LLM verifier 只生成建议、不覆盖原始质控结果, so that 质控链路可审计。
10. As an 开发人员, I want 复核报告保存在任务 summary 中, so that 第一版不引入复杂表结构。
11. As an 管理员, I want HTML 导出同时包含质控结果和复核建议, so that 可以离线留存和客户沟通。
12. As an 实施人员, I want 复核第一版仅支持 LX0609, so that 不会把其他规则集口径混入当前交付。

## Implementation Decisions

- 第一版仅支持 `luxian_0609_qc_v1`。
- 触发方式为手动点击 `复核本次结果`。
- 新增后端复核接口：`POST /api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/review`。
- 复核报告保存到任务 `summary.review_report`。
- 不新增数据库表，后续如稳定再考虑独立 `qc_result_review_reports` 表。
- 复核分两层：
  - 规则化 verifier：检查硬性风险。
  - LLM verifier：仅复核规则化 verifier 标出的风险项或语义类风险。
- LLM 输入只包含质控点 ID、质控点名称、原始状态、结论摘要、证据片段、缺失字段、来源文书和来源字段。
- LLM 不接收完整病历全文、`prompt`、`raw_response`、`embedding`、`bundle`、`documents`。
- LLM 输出只作为复核建议，不修改原始状态。
- 风险等级内部使用 `P0/P1/P2`，前端展示为：
  - 高风险：疑似误判。
  - 中风险：建议人工复核。
  - 低风险：展示可优化。
- 前端展示位置：
  - 任务中心：显示复核摘要。
  - 结果抽屉：内嵌复核报告。
  - HTML 导出：追加复核报告章节。
- 不新增单独的复核中心页面。

### 第一版规则化 Verifier 范围

1. 适用性门控风险：
   - 会诊类无会诊申请、会诊记录、会诊意见等强证据。
   - 输血类无输血医嘱、输血申请、输血记录或收费血制品等强触发事实。
   - 化疗类无化疗医嘱或化疗记录。
   - 四级手术讨论类未证明为四级手术。
2. 状态和结论矛盾：
   - 状态为 `non_compliant`，但结论包含“符合”“未超过”“已记录”“未违反”等正向表达。
   - 状态为 `compliant`，但结论包含“缺失”“未见”“超时”“不完整”等缺陷表达。
3. 数据不足展示风险：
   - `data_gap` 没有列清楚缺失字段。
   - `data_gap` 被展示为“轻微缺陷”“严重缺陷”等正式缺陷标签。
4. 证据质量风险：
   - 证据片段过短。
   - 无来源文书。
   - 无字段、时间、阈值、实际值或差值。
   - 证据中仍含内部词：`LLM`、`raw`、`evidence`、`映射执行规则`、`证据模板`。
5. 多病历可读性风险：
   - 结果缺少 `visit_id`、患者、科室等病历标识。
   - 多病历结果未按病历分组。

### 复核报告建议结构

```json
{
  "review_status": "completed",
  "reviewed_at": "2026-07-05T00:00:00+08:00",
  "scope": "luxian_0609_qc_v1",
  "summary": {
    "total_findings": 6,
    "p0": 1,
    "p1": 3,
    "p2": 2
  },
  "findings": [
    {
      "rule_id": "LX0609-020",
      "rule_name": "会诊记录：有会诊记录单无请会诊执行记录",
      "record_id": "2329756",
      "original_status": "uncertain",
      "suggested_status": "not_applicable",
      "severity": "P1",
      "risk_type": "applicability_gate",
      "reason": "未发现会诊申请单、会诊记录单或会诊意见等强触发事实。",
      "customer_message": "当前病历未见会诊文书证据，本项不宜作为会诊执行问题展示。",
      "requires_human_review": true,
      "auto_applied": false
    }
  ]
}
```

## Testing Decisions

主要测试 seam：

- 后端以 `POST /batch-jobs/{job_id}/review` 为最高测试入口。
- 前端以任务中心和结果抽屉为主要行为 seam。
- HTML 导出以导出结果文本内容为测试 seam。

后端测试重点：

- 非 LX0609 任务不允许复核或返回明确提示。
- LX0609 任务能生成 `summary.review_report`。
- 会诊无强证据时生成“建议不适用”的复核建议。
- `data_gap` 输出“数据不足/需人工复核”，不作为正式缺陷。
- 状态和结论矛盾时标记高风险。
- 复核报告不包含敏感字段。

前端测试重点：

- 完成任务显示 `复核本次结果`。
- 点击后能展示复核摘要。
- 结果抽屉能展示高、中、低风险分组。
- HTML 导出包含复核报告。
- 未生成复核报告时页面不报错。
- `data_gap`、`uncertain`、`not_applicable` 不显示成合规或正式缺陷。

建议验证命令：

```powershell
cd D:\LLM\LX888\apps\medqc-web
npm run test:unit -- --pool=threads tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
npm run test:unit -- --pool=threads tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
npm run type-check
npm run check:encoding
git diff --check

cd D:\LLM\LX888\apps\medqc-web\backend
python -m pytest tests/unit/test_qc_sichuan_batch_throughput.py tests/unit/test_luxian_0609_mainline_services.py -q --confcutdir=tests/unit
```

## Out of Scope

- 不自动修改原始质控结果。
- 不自动修复规则代码。
- 不支持非 LX0609 规则集。
- 不新增 parent-job / child-job 后端模型。
- 不新增复核报告独立数据库表。
- 不导出完整病历全文。
- 不把复核建议作为正式医疗质控结论。
- 不宣称真实客户样本准确率达标。

## Further Notes

第一版目标不是“让 AI 自动判对”，而是建立一个可审计的结果复核闭环：

```text
质控任务完成
-> 手动复核
-> 规则化 verifier 找风险
-> LLM verifier 给建议
-> 保存 review_report
-> 前端展示 / HTML 导出
-> 人工决定是否修规则或人工复核
```

建议后续拆成 4 个实现任务：

1. 后端复核接口与 `summary.review_report` 写入。
2. 规则化 verifier。
3. LLM verifier 和输入脱敏边界。
4. 前端任务中心、结果抽屉、HTML 导出接入复核报告。
