# 失败配对恢复 POC 结论

原型保存在独立分支 `codex/poc-failed-rule-recovery-20261015`，提交 `35cb9b322`。工作树为 `D:\MedQC-worktrees\poc-failed-rule-recovery-20261015`；正式集成分支未合入原型代码。

运行 `py -3.10 apps/medqc-web/backend/prototypes/failed_rule_recovery_poc.py --output apps/medqc-web/.tmp/failed-rule-recovery-poc`，生成独立 HTML 演示和 JSON 记录。可直接打开的演示副本在 `D:\medqc-build\failed-rule-recovery-poc.html`，运行报告副本在 `D:\medqc-build\failed-rule-recovery-poc-report.json`。

合成验证结论：

- 05-01-03 可以由程序冻结文书与药物配对，逐项复用正式 `_assertions` 原文核验，保留通过项，只补未通过项一次。漏项不默认视为 absent，unknown 不生成确定结论；重复配对、伪造引文和补查改写既有事实均不被采信。8 个场景的运行验收条件通过。
- 03-01-04 可以在 HTTP、解析、协议和程序边界区分错误，9 种合成异常分类符合预期，报告不包含异常文字、请求地址或注入的模拟秘密。分类只建议哪些属于瞬时错误，未增加正式补跑次数。
- 页面已实际操作首轮保留3项、只补P04、补查仍缺P04以及本地类型错误分类；显示与 Python 运行状态一致。9份已有成功结果为内存演示对象，不代表持久化或正式API验收。

真实模型调用0，数据库连接0。Ruff和编码检查通过，ESLint无错误（1361项既有警告）。未新增单元测试框架、运行前端全量测试或类型检查；原型以单命令运行内置验收条件。未构建交付包、更新客户机或更改正式执行链。

该 POC 支持“逐项核验、只补缺项”和“异常按阶段分类”两项设计决策。正式落地仍需把补查范围写进模型输入协议，并接入现有自动补跑总预算、Token 核算及交付合同，再用客户失败配对定向验证。不能据此确认历史会诊错误根因或声称真实模型准确率/恢复率已改善。
