# PR 说明：0609 质控引擎集成分支合入 business-agent 集成线

- 来源：`codex/qc-integration-20261008`
- 目标：`codex/business-agent-integration`（`130bddd78`）
- 仓库：`softjazzz/combined`
- 建议以 Draft PR 提交，审阅通过后快进合并。

## 合并方式

来源分支已包含目标分支的全部提交（目标分支领先 0），可直接快进合并，无冲突。
同时已包含 `codex/lx0609-tech-debt-20260730` 与 `codex/customer-preflight-20261006`。

范围：231 个提交（2026-10-06 至 2026-10-12），761 个文件。其中约 574 个为文档或测试，
116 个为后端应用代码，56 个为前端源码。

不要用 squash：提交历史里保留了逐条规则的口径变更记录，后续核对口径依赖它。

## 主要改动

### 1. 0916 验收与客户包（10-06 至 10-07）

- 0916 任务模型成本累计、危急值明细身份、同步索引字段与实际迁移。
- 客户验收候选代码冻结、客户包预检失败收敛、工作簿导出保留完整长文本。
- 基础时限权威时间的时区兼容（已在 PG 上重跑验证）。

### 2. 0609 逐规则修复（10-07 至 10-11）

按院方口径和业务基线逐条修复，覆盖以下规则族：

- 术前小结、术前讨论、手术记录时限、术者查房（029/030/039/040/064/078）
- 麻醉访视（036/037；037 因源库不提供访视记录暂停）
- 输血（043–048/070，按已开输血医嘱触发）
- 化疗（026，药物-动作-剂量原子绑定）
- 病理（013/019，模型给原文引用、程序核验）
- 抗菌药物（054/055/056/028）
- 诊断（018/050/074/077/08-01-03）
- 死亡相关（060/076/09-01-02/09-02-01）
- 会诊（03-01-xx，含新增"会诊措施逐项核对"）
- 检查检验（06-01-01 至 06-01-05、06-03-02）
- 出院（062/068/08-01-05）

共性改动：

- 结构化抽取统一关闭 thinking、固定温度 0。
- 协议违规时带提示重试 1 次；网络/上游临时错误重试。
- "原文引用 + 程序核验"取代字符坐标协议。
- `uncertain` 尽量改为资料不足或明确结论后再交付。

### 3. 隐私网关（贯穿）

- 发送前身份核验、已知身份残留拦截（含 JSON 转义换行绕过）、地址/单位脱敏修复。
- 预生产病例发送作用域与失效拒发。

### 4. 本轮收尾（10-12）

- **06-01-04 报告结果记录**：改为逐份病程核对，模型摘一句原文，程序核验它出自病程且与本次报告内容对得上。
  - 超时提示改为"已记录但超过 24 小时"。
  - 新增"检查结果与病程一致性"核实提示：病程对结果的描述与报告矛盾时，这份病程不计入，并另行提示核实。
  - 出院当天的病程计入，出院记录不计入。
- **测试与 CI**：
  - 0609 测试去除执行顺序与环境依赖，历史失败从 114 个清零。
  - 新增独立工作流 `.github/workflows/lx0609-quality-gate.yml`：零模型、临时 SQLite，触发分支含本目标分支。
  - `requirements.txt` 补齐运行时缺失包，门禁只按清单安装。
- **质控规则页**：规则详情新增"引擎判定说明"，逐条说明何时判定、判定步骤和各结论含义。
  - 数据源为 `backend/app/data/luxian_0609_engine_judgment_v1.json`（72 条可执行，8 条暂停，5 条不在交付范围）。

## 验证

本地（Windows，Python 3.10），未调用模型，未连接业务库：

```bash
cd apps/medqc-web/backend
PYTHONHASHSEED=0 DATABASE_URL=sqlite:///<临时目录>/x.db JWT_SECRET=local-test-only-secret-0123456789abcdef \
  python -m pytest tests/unit/test_luxian_0609*.py tests/unit/test_n10_*.py tests/unit/test_qc_llm_client*.py \
  tests/unit/test_verify_consultation_family_acceptance.py tests/unit/test_qc_diagnostic_session_restore.py \
  tests/unit/test_qc_diagnostic_session_redaction.py -n 8 -q -o addopts="" -p no:cacheprovider --timeout=180 -W ignore
```

- 结果：9465 通过，1 跳过。这是 Claude 本地运行的结果，尚未独立复验。
- 质量门禁：`python scripts/run_luxian_0609_quality_gate.py --profile pr-no-model`，在按 `requirements.txt` 新建的虚拟环境中通过。
- 前端：`check:encoding`、`lint`、`type-check` 通过；规则详情相关单测通过。
  - `test:unit` 全量有 3 个与时区相关的既有失败（date-utils、QCOverviewView），与本 PR 无关。
- GitHub Actions 上的门禁尚未确认运行结果，合并前需看到本 PR 上的门禁通过。

真实模型（qwen3.8-flash）验证仅限定向：06-01-04 在有 CT/MRI 事件的病例上跑了两组、每组 3 轮，均无翻转。

## 已知遗留（合并前须知）

1. **偶发翻转未解决**：06-01-02 C09、06-01-05 C12、06-01-01 C06/C20、03-01-04 C26，多轮运行中结论偶有不一致。
2. **未跑完整真实模型回归**：80 条规则（可执行 72 条）的全量多轮真实回归尚未执行。
3. **"引擎判定说明"文案未经业务审核**：手术麻醉、输血、抗菌药物、肿瘤病理几组最需要审。
4. **062 展示问题**：完全相同的重复医嘱行会被重复计数，只影响展示，不影响判定。
5. **院方待确认**：仍有待定口径和缺源暂停规则，见 `apps/medqc-web/docs/0602/LX0609-院方待确认清单-v1.md`。

## 不在本 PR 中

- 工作区未跟踪文件均未提交：意见冻结目录、输血复现用例 JSON、两份研究文档、`.claude/launch.json`。
- 含患者原文的审计材料只在本机 `.tmp/` 下，不入库。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
