# 质控规则示例生成与维护指南

## 目标
为四川省 146 条住院病历质控规则提供“正例/反例”的定制化病历示例，支撑前端一键演示与回归测试。

## 示例设计原则
- 面向规则：每条示例紧扣该规则的约束与判定点，禁止通用模板。
- 医学真实：章节、语句、时间轴与术语合理可信，避免虚假医学事实。
- 纯正文：不包含“注意/说明/分析”等提示性文案，只保留病历正文。
- 长度控制：按复杂度分级控制长度（低 300–500；中 500–800；高 800–1200 字）。

## 规则类型与策略
- 存在性检查：
  - 正例：要素齐全；反例：关键字段缺失或整个记录缺失。
- 时效性检查：
  - 正例：时间戳满足要求；反例：明显超时或记录时间在逻辑上错误。
- 一致性检查：
  - 正例：主诉/现病史/诊断前后一致；反例：存在否定矛盾或跨系统冲突。
- 完整性检查：
  - 正例：包含所有必填项；反例：缺少必填章节或内容空泛。
- 规范性检查：
  - 正例：格式/签名/日期规范；反例：格式混乱或签名缺失。

## 文书结构模板
- 入院记录：基本信息、主诉、现病史、既往史、查体、辅助检查、初步诊断、诊疗计划
- 病程记录：日期时间、病情变化、诊疗措施、医嘱调整、医师签名
- 出院记录：入院日期、出院日期、入院诊断、出院诊断、诊疗经过、出院医嘱
- 手术记录：手术日期、手术名称、术者/助手、麻醉方式、手术过程、术后评估
- 知情同意书：项目名称、风险告知、患者签名、医师签名、日期

## 数据结构
```ts
export interface QCRuleCaseExample {
  title: string
  summary: string
  sections: { heading: string; content: string }[]
  focusPoints: string[]
}
export interface QCRuleCase {
  ruleId: string
  documentType: string
  positive: QCRuleCaseExample
  negative: QCRuleCaseExample
}
```

## 生成与合并
- 生成器：`/tmp/generate_rule_examples.py`（mock/llm）
- 合并器：`/tmp/merge_examples_to_typescript.py`
- 输出文件：`/tmp/qcRuleCases_new.ts`

### 分批命令示例（mock）
```bash
python3 /tmp/generate_rule_examples.py --range 001-037 --mode mock --out /tmp/examples_001_037.json
python3 /tmp/generate_rule_examples.py --range 038-074 --mode mock --out /tmp/examples_038_074.json
python3 /tmp/generate_rule_examples.py --range 075-111 --mode mock --out /tmp/examples_075_111.json
python3 /tmp/generate_rule_examples.py --range 112-146 --mode mock --out /tmp/examples_112_146.json
python3 /tmp/merge_examples_to_typescript.py
```

### LLM 模式
设置：`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`MODEL=qwen3-30b-a3b-instruct-2507`，`--mode llm` 即可。

## 集成与验证
- 备份并替换：`apps/medqc-web/src/data/qcRuleCases.ts`
- 前端函数：`getExampleMedicalText` 已改为只依赖 `qcRuleCaseMap`，未命中则提示“暂无示例”。
- 前端验证：
  - 规则管理 → 打开“测试”弹窗 → 切换“正例/反例”
  - 使用“开始测试”验证合规/不合规判定（依赖 LLM）。

## 质量抽检
- 每个分组抽 3–5 条（共 ~15 条），覆盖存在性/时效性/一致性/完整性/规范性等类型。
- 检查：是否合规/违规正确；是否无说明性文字；医学事实合理。
- 问题处理：记录问题模式，批量修正生成策略或直接修订对应条目。

## 风险与建议
- 生成质量：建议医疗专业人员参与审核关键规则；保留 mock 兜底。
- 数据一致性：四个分组输出需严格校验结构，合并时已做必填项验证。
- 性能：若示例数据过大导致首次加载慢，可按文书类型拆分或改为后端按需拉取。

