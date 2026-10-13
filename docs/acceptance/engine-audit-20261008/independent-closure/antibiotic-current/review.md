# 抗菌 054/057 既有成果当前证据绑定

指定 13 项明确合成材料已在固定 `21f4a93e103a34002a1f9d36f9d895f226c0122f` 完成回放：13 项无异常、13/13 与旧 observed 一致、8/13 满足原 expected，5 项原有差异保留。限定合成来源 manifest 缺口已补齐，没有新增产品发现或修改医学样例。退出 0 表示支撑运行完成和边界检查满足，不代表 13 项临床合同全绿或部署通过。

仅 LX0609-05-01-02/05（legacy054/057）；未扩展审其它抗菌或全规则。准确旧审阅报告是 `apps/medqc-web/docs/acceptance/2026-10-07-round2-antibiotic-audit.md`，覆盖账对应根 `docs/acceptance/engine-audit-20261008/tumor-pathology.json` 的 `/rules/1` 和 `/rules/4`。旧报告的 A-01/A-02 来自更早快照；当前回放绑定的是后来 antimicrobial 合成审阅的原材料/原预期/原 observed，不能直接将早期缺陷观察写成当前回退。没有打开报告提及的私有目录，没有重读真实材料或继承其 PG/.env 读取方法。

## 精确输入与结果

| 原 case 索引 | 规则尾号 | 合成边界 | 原 expected | 旧及当前 observed |
| --- | --- | --- | --- | --- |
| 0 | 02 | 明确培养感染理由 | compliant | compliant |
| 1 | 02 | 理由未记录 | non_compliant | non_compliant |
| 2 | 02 | 拟使用、后续评估 | not_applicable | technical_error |
| 3 | 02 | 今日未使用 | not_applicable | technical_error |
| 4 | 02 | 停用理由未记录 | non_compliant | non_compliant |
| 5 | 02 | 未纳入硬编码目录的头孢噻肟 | data_gap | not_applicable |
| 13 | 05 | 取消医嘱且未实际给药 | not_applicable | not_applicable |
| 16 | 05 | 胸部影像证实细菌性肺炎 | compliant | compliant |
| 17 | 05 | 尚不能证实细菌性肺炎 | non_compliant | non_compliant |
| 18 | 05 | 经验用药理由未记录 | non_compliant | non_compliant |
| 19 | 05 | 无痰标本可采 | compliant | non_compliant |
| 20 | 05 | 日常病程的经验用药实施描述 | non_compliant | non_compliant |
| 21 | 05 | 相同描述放入会诊来源 | non_compliant | not_applicable |

02 六项中 3 项符合原预期，05 七项中 5 项符合原预期。case 2/3 精确继承 `TP-L01`，reason_code 是 `model_transport_error`：没有提供模型时语义候选失败关闭，不能声称未使用/拟用的真实语义已被验证，更不能据此确认语义误判。case 5 是既有 `TP-Q03` 药品目录范围风险：原合成冻结采取保守 `data_gap`，实际仍 `not_applicable`；本项没有医院完整药品目录及批准代码映射证据，不能将该差异升级成已确认漏掉客户冻结目录内药品的产品缺陷。case 19 精确继承 `TP-Q05` 无样可采原因充分性，case 21 精确继承 `TP-Q04` 会诊来源口径。当前均复现旧观察，保留为原限制/争议，不修改 expected 制造全绿，不开新重复 issue。

## 固定源码和消费边界

原文件 `antimicrobial-expectations.json`、`antimicrobial-results.json`、`antimicrobial_probe.py` 及其 import 依赖 `probe.py` 的完整副本和 SHA256 保存在本目录。输入/结果 id、rule 按原索引逐项核对。`cases.json` 只抽取指定 13 项，保留原 rows、expected、observed；冻结 SHA256 `032b456895aa2eedfb54598171f8d324febe4d86380e40b5a4a2c23538ad5e5f`。`case-bindings.json` 给出每项输入/result 的原 JSON pointer、原对象 hash、当前 result pointer/hash 和生成脚本关系。

当前固定 app Git tree 与 727 文件内容 hash 记录在 `manifest.json`。运行前后全部源 hash 一致。实际加载 app namespace 的 171 项中，168 个真实模块文件的绝对 source path/SHA256 全部命中 manifest；另外 3 项是已声明的 `app`、`app.services`、`app.services.luxian_0609` package initializer suppression。没有 app 模块从主工作树悄悄导入，没有 AST 摘录生产判据或伪造 app 依赖实现。`results.json` 逐项保存实际加载模块及 provenance 结果。

真实内存消费顺序：固定既有 unit helper `_session` 建造合成 SourceObservation/Material Store → 完整正式 native extended-document executor → 正式 binding/reducer → canonical Finalizer。原脚本的 DB stub/较宽 bootstrap guard 没有沿用。该 unit helper 直接构造材料，未执行正式来源 collector/provider；回放没有运行 Worker、Store/SQLite 保存、API/浏览器或客户端点。正常/缺理由、否定理由、取消未执行的合成工程边界可以绑定到当前源码，但不增加真实适用病例覆盖。

## 实际执行与隔离

命令 `python F:/MedQC-worktrees/review-artifacts/antibiotic-evidence-current/replay.py`。attempt 2 实际 exit 0，进程 3.086 秒，13 项主循环 0.984 秒；无病例异常、无 source provenance 错误、无源漂移、无外部边界尝试，每项 `llm_call_count=0`。

runner 在 guard 前仅预热标准库 Windows platform 探测；其后清空本子进程环境，使用合成 JWT/空 DATABASE_URL，关闭 dotenv 函数，阻断 `.env` 文件读取、PG driver、所有 SQLAlchemy Engine.connect 与外部 socket。只在调用栈精确包含标准库 `socket.py/socketpair` 时允许 Windows asyncio self-pipe，没有普通 localhost 豁免。禁止写 source/ 和 artifact 目录之外；结果仅写本独占目录，没有生产、共享测试或他人报告修改。

attempt 1 在 asyncpg import → platform/subprocess 首次探测时，guard 误拦标准 Windows nul sink，0 病例执行、exit 1。按根建议预热纯标准库 platform 后再运行，最终 guard 未保留 devnull 设备例外。`support-failures.json` 保留首轮支撑错误；它不是规则失败，也未计为有效观察。两轮均没有 PG/网络连接或真实模型调用。唯一测试槽在 attempt 2 结束后立即释放。

## 完成层级与剩余门禁

本项完成的是指定历史合成证据在当前固定源码上的来源绑定及最小回放；两条规则不是“未审”，也不能因证据绑定完成就称全部临床验收通过。旧 expected 的 5 处限制仍开放；真实语义模型、医院药品目录、实际来源采集、无样可采/会诊范围口径及完整客户链均未由此完成。最终候选后续源码变化需要按依赖相关性复核或重放，本报告只固定上述 SHA。

主要索引：`review.json`、`manifest.json`、`case-bindings.json`、`cases.json`、`results.json`、`replay.py`、`support-failures.json`、`historical-report.fixed.md` 和 `ledger-selected-rules.json`。回放脚本 SHA256 `5f97067765f6b7066a54bb6d0d412f161fa1c1815a9ed2aa8e334711c5c780ee`；结果 SHA256 `406fa9f9dd675e5faf2722c802294237256ff960be89bf813a7390f660aa0155`。
