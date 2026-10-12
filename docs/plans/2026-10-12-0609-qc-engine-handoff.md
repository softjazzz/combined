# 0609 质控引擎交接报告（2026-10-12）

接手人先读本文，再读 `apps/medqc-web/docs/0602/泸县0609质控点-业务标准基线-v1.md`（权威口径）。Codex 台账只作线索。

## 1. 位置与状态

- 分支：`codex/qc-integration-20261008`（已推送 github `softjazzz/combined`），最新提交 `badf58bb9`。
- 原工作树：`F:/MedQC-worktrees/qc-integration-20261008`（F 盘移动硬盘）。D 盘主仓库 `D:/LLM/LX888` 当前在别的分支，见第 7 节迁回步骤。
- 规则集：`luxian_0609_qc_v1`；代码在 `apps/medqc-web/backend/app/services/luxian_0609/`。
- 模型：默认 `qwen3.8-flash`（DashScope）；0609 抽取在隐私网关处固定温度 0。
- 不要暂存的未跟踪文件：`backend/data/luxian_0609_opinion_freeze/`、`backend/tests/unit/phase5_transfusion_reproduction_cases.json`、`docs/acceptance/engine-audit-20261008/*.md`。

## 2. 常驻约束（用户要求）

- 中文沟通；提交信息中文，结尾 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；只按整文件暂存。
- UTF-8 无 BOM、LF；提交前 `npm run check:encoding`（在 `apps/medqc-web`）。
- 业务库只读；写库、删除、强推、全局安装须明确授权。普通 `git push` 已授权。
- 凭据只从 `D:/LLM/LX888/apps/medqc-web/backend/.env` 读取，不得打印或写入文件。
- 不按病例/文书 ID 硬编码，不用样本词表。真实模型调用前先报模型和调用量。
- 含患者原文的文件只放 `apps/medqc-web/.tmp/0910-full-audit/`，以 `-private` 结尾，不提交。回复只用别名 C01–C30，不提患者或医生姓名。
- `uncertain`、`technical_error` 尽量不交付。

## 3. 本阶段已完成（按提交）

| 提交 | 内容 |
|---|---|
| 07d2a20d0 / 11405dedc / 9e8a4499d | 06-01-02：写明部位及要了解/观察的情况才算原因；“完善CT”“复查MRI”无部位目的不算；检查前 48h 窗口无病程→程序判未写原因；CT 引导下操作→程序判不适用 |
| 07d2a20d0 / 11405dedc | 06-01-05：只罗列或罗列后直接下诊断不算分析；附带发现（钙化、退变、随诊微小结节）不要求分析；模板式鉴别诊断不算 |
| 4f2ddaa22 | 06-01-05：新增前置相关性判定 `exam_finding_relevance.py`（每例 1 次调用），结论由程序固定为事件阳性提示，主抽取不得改判 |
| 3f650f3d1 / e0db6d5e9 | 08-01-05：重要住院事件由程序从结构化来源确定（手术、已回报病理、输血、抢救、转科、危急值），模型只做 A（出院记录自身）与 C（是否提及）；重试附违规提示 |
| d65f5ca76 | 04-05-02/08-02-01 病程正文抽取：引文限一句 40 字内，违规带提示重试 1 次 |
| badf58bb9 | 03-01-04：按明确执行事实判定，不再以模型自评置信度降为资料不足 |
| 5b84b05cd | 0609 隐私网关：超时、连接失败、上游 429/5xx 重试 1 次（间隔 2 秒） |
| 9e8a4499d | 共享客户端 `generate` 增加可选 `temperature`；0609 网关在下游支持时固定传 0 |
| 5f2c913ea | 050/074/输血触发抽取：协议违规重试 1 次 |
| e855b18a6 | 恢复执行 056（7 类 25 种重点抗菌药）、028（Ⅰ类心脏 48h，其余Ⅰ/Ⅱ类 24h，超时有感染证据视为转治疗） |

规则口径已同步到 `backend/app/data/luxian_0609_rule_master_v1.json`（policy_summary ≤240 字，超长会让全部用例失败）和业务基线文档。

## 4. 稳定性现状（0910 样本 30 例，温度 0）

- 08-01-05：多轮一致（合规 20 / 不合规 10）。
- 06-01-03、06-01-04：基本一致（06-01-04 偶有 1 例）。
- 06-01-05：加前置判定后两轮差 1 例（C16，属“模板式鉴别算不算分析”的边界）。
- 06-01-02：3 轮温度 0 中 1–3 例翻转（C04、C12、C23），属“复查MRI”类边界及模型越窗引用。用户决定暂不做“越窗引用直接判未写原因”。
- 03-01-04：改门槛后尚未用真模型复测（预期 C02、C13 稳定为不合规）。

## 5. 进行中：多模型对比（被额度中断时正在跑）

- 目的（用户想法）：不必全部质控点用同一模型；不稳定的抽取组试用其他模型，若更稳可按“抽取组→模型”混用。
- 院方已允许数据外发给 DeepSeek。候选：`deepseek-flash`（用户称 Flash V4.1；接口 `/models` 列出 `deepseek-flash`、`deepseek-v4-pro`）、`qwen3.6-35b-a3b`（须用 `DASHSCOPE_API_KEY` + `DASHSCOPE_BASE_URL`，`LLM_API_KEY` 返回 401）。
- 私有跑批脚本已支持 `LX0910_MODEL=deepseek-flash|qwen3.6-35b-a3b`（不设即默认 qwen3.8-flash）；`api.deepseek.com` 已在出网白名单；本机到 DeepSeek 偶有连接超时，网络重试可兜住。
- 已在后台启动三模型并行、各 3 轮（规则 `LX0609-06-01,LX0609-03-01,LX0609-08-01-05,LX0609-04-05`，约 1,600 次调用）。日志：`.tmp/0910-full-audit/b-recheck-20261010-private/mc-<模型>-private.log`，每份末尾 `ALLDONE` 表示完成。若中断未完成，重跑即可。
- 汇总：把三份日志合并后执行 `python model-compare-private.py <合并日志>`，输出各模型多轮不一致数及模型间分歧。下一步：逐例人工核对分歧，给出“哪组用哪个模型”的建议；用户同意后再在 0609 网关加“抽取组→模型”路由配置（每次调用记录实际模型）。
- 注意粒度：06-01-02/04/05 共用一次调用，只能按抽取组选模型。

## 6. 测试与工具

- 全量回归（已装 pytest-xdist 3.8.0）：在 `apps/medqc-web/backend` 执行
  `PYTHONHASHSEED=0 DATABASE_URL=sqlite:///<临时目录>/x.db JWT_SECRET=local-test-only-secret-0123456789abcdef python -m pytest tests/unit/test_luxian_0609*.py tests/unit/test_n10_*.py tests/unit/test_qc_llm_client*.py -n 8 -q -o addopts="" -p no:cacheprovider --timeout=120 -W ignore`，约 7–8 分钟。
  必须固定 `PYTHONHASHSEED`，否则 xdist 收集不一致。
- 当前并行结果：102 个失败，均为历史遗留（含 `test_luxian_0609_canonical_result_delivery.py` 一组依赖执行顺序的用例，单独跑也失败）；最近几次改动均无新增失败。
- 私有跑批：`.tmp/0910-full-audit/b-recheck-20261010-private/run-private.py dry|live [别名...]`，环境变量 `LX0910_RULES`（逗号分隔前缀）、`LX0910_SKIP`、`LX0910_CASES`、`LX0910_MODEL`。数据库连接强制只读。脚本内写死了 F 盘路径 `APP = F:/MedQC-worktrees/...`，迁回 D 盘需改。
- 辅助脚本（同目录）：`compare-private.py <旧> <新>`、`detail-private.py <run> <规则后缀> [状态]`（输出为 GBK，需 `iconv -f gbk -t utf-8`）、`events-by-run-private.py`、`reason-snippets-private.py`、`consult-dump-private.py`、`events0805-private.py`、`model-compare-private.py`。
- Bash heredoc 里含 `\n` 的 Python 容易被改坏，复杂补丁先用 Write 写脚本文件再执行。

## 7. 待办（优先级从高到低）

1. 完成多模型对比并出建议（第 5 节）。
2. 03-01-04 真模型复测 1 轮（约 30 次调用；对比中 qwen3.8 那 3 轮也可用）。
3. 清理 102 个历史失败用例，把 0609 测试接入 CI；再向 `push-fix-clean` 提 PR。
4. 等院方：020–022、036、037 缺源数据（保持暂停）；028 等医嘱停止时间同步；025/059 待验收。
5. 安全：本会话中列 `.env` 配置时本地数据库连接串（含密码）曾出现在工具输出中，已提醒用户更换。
