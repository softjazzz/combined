# 0609 07族第一轮审计归档

固定版本：`7b894dc84491b7b72eb096de58fe61f772cc0080`。实际目录为8条输血相关规则；文件名是分工标签。用户已排除0916，既有观察保留在探针文件且标记`scope_excluded_by_user`，不计分母、阻断或完成率。

## 结论与边界

已有离线结果收敛为3类P1残留。10个独立合成场景4符合冻结预期、6出现差异；不是临床准确率或10个真实病例。只读当前生产源码，0真实模型、0PG读写、0生产/共享测试修改、0新增pytest。恢复本轮后只归档既有证据，没有重头审查。

0609采用原源码AST纯函数依赖闭包；070复现当前分支的同构输入字典。未执行完整Typed、Finalizer、保存、API或浏览器链。`observed-results-first-run.json`及首轮脚本保留工具修正前后出处；冻结业务状态预期没有随输出调整。

## P1残留

1. **TC-01：专用输血记录长度把计划/拒绝/暂缓判成已实施。** `native_transfusion_execution.py:2865`排除少数取消/未输血短语后，仅正文长度≥16即确认实施。`TF_PLAN`、`TF_REFUSED`、`TF_POSTPONED`为`present`；计划记录还进入046纯函数，输出`non_compliant/transfusion_purpose_or_indication_missing`。影响共同门控后的07-01-01、07-01-02、07-02-01、07-02-02、07-03-01。明确取消=`data_gap`、实际输注且无反应=`present`正常对照保留。先修事件事实，不能按测试句打关键词补丁。
2. **TC-02：070取消输血记录的完成时间被当作实际输血时刻。** `native_extended_document_execution.py:3001`合并所有专用记录为`actual_transfusion_rows`；九项函数使用`native_transfusion_execution.py:961`的`record_time`回退。明确取消、仅有记录时间、入院时间及完整空检验输入，纯重放得`non_compliant/pretransfusion_items_incomplete`，同时写`performed_transfusion_confirmed=true`。应保留无法确认实施的`data_gap`，完成时间不可单独证明实际输血。该结果是分支输入/纯函数证据，不称070正式整链复现。
3. **TC-03：048否定术中输血及备血量仍生成术中输血差异。** `native_transfusion_execution.py:2388`的正向触发未排除否定/备血。三份文书均明确“术中未输血”，2U/4U/2U只是术前备血，仍输出`non_compliant/transfusion_records_inconsistent`及`performed_intraoperative_transfusion_confirmed=true`。若本次住院其他阶段已有实际输血，共同门控也不能证明术中实施；本轮未运行该整链组合。

## 已关闭成果与正常对照

- **048 `b4a98783e`已修成分与紧邻剂量配对/比较合同，保持关闭。** 新TC-03是触发事实残留，不重开配对问题。本轮`048_MATCHED`的2U/2单位一致为合规；`048_TIME_CONFLICT`明确不同事件时点为`data_gap/association_failed`。旧修复索引为`2026-10-08-isolated-qc-integration.md:17`，同文`:22`记录集成482项通过、`:24`给出F:/MedQC-worktrees/review-artifacts各组独立复核路径；组别精确产物由总索引继续绑定，这两个离线对照不替代旧复审。
- **044字段/客户事实合同保持关闭。** 本轮TC-01与多事件/逐次输血申请关联未闭环独立列项，缺当前真实复验不等于未审。关闭SHA为`db4bddb67`，精确公开证据`2026-10-08-isolated-qc-integration.md:18`；同文`:24`记录独立合同182项及正式执行/SQLite/新引擎/API投影12项通过，`:32`明确044三项多事件候选在基线亦失败，仍未关闭。另保留`2026-09-06-lx0609-transfusion-family-convergence.md`职责/合同证据。
- **049暂不执行边界保留。** 实际07-04-02目录为`pending_definition`，客户范围没有可用收费来源；不能因未执行或缺真实病例记为临床失败。

## 逐规则归档

| 规则 | 实际名称 | 本轮残留 | 已有成果/边界 |
| --- | --- | --- | --- |
| LX0609-07-01-01 | 输血前常规检查不完整 | TC-01 | 已检查家族门控及九项确定性函数；本轮未新增九项真实样本复核。 |
| LX0609-07-01-02 | 无输血前评估记录或记录不完整 | TC-01 | 044既有字段/客户事实合同已关闭；本轮新门控问题与多事件/逐次申请关联未闭环分别记录，不能重开已关合同。 |
| LX0609-07-02-01 | 无输血病程记录 | TC-01 | 当前取消/实施无反应正常门控对照保留；计划/拒绝/暂缓误实施残留。 |
| LX0609-07-02-02 | 输血病程记录不完整或不规范 | TC-01 | 计划记录可进入046不合规分支；现有逐份字段合同和成分最小抽取未在本轮重测。 |
| LX0609-07-03-01 | 无输血后评价 | TC-01 | 实际实施前提受共同门控残留影响；24小时窗与逐次评价关联本轮仅既有源码边界，未新测。 |
| LX0609-07-04-01 | 术中输血三份文书内容不一致 | TC-03 | 048 b4a98783e配对/合同已关闭；单位归一和时点冲突本轮正常对照通过，否定/备血触发单列新残留。 |
| LX0609-07-04-02 | 输血医嘱与收费不一致 | 暂不执行 | 当前目录phase_status=pending_definition：客户范围无可用收费数据，规则暂不执行。保留排除，不以未执行计算临床失败。 |
| LX0609-07-01-03 | 输血前评估：未做输血前相关九项检查 | TC-02 | 扩展070实际由extended_document执行，未经过普通家族取消门控；不能按编号或栏目猜执行器。 |

除客户暂不执行的07-04-02外，本组未核验范围匹配的独立真实冻结反例输入SHA；本轮没有真实模型。医学/业务判据没有新争议，计划、拒绝、否定和实际实施是不同事件事实，不能据未验收推断业务标准未定。07-04-01公开2026-10-08记录明确欠实际输血、手术、麻醉、术后首次病程完整组合；沿用该样本缺口，不冒充重新盘点。

## SHA与证据出处

本轮冻结合成预期在执行前保存，哈希及观察产物如下；主冻结文件还含用户后来排除的0916预期，当前有效场景仅JSON中的`probe_results`十项。

- `.tmp/engine-audit-20261008/treatment-consultation/frozen-expectations.json`：`40fa02375634a4393cadccb439e79c466d114fb2ea7e8156888dcfac1d3a8371`
- `.tmp/engine-audit-20261008/treatment-consultation/extension-frozen-expectations.json`：`3077945601ca54174a167f1070bff8bc8788f1eabbdee598d29cde9bbb776303`
- `.tmp/engine-audit-20261008/treatment-consultation/048-frozen-expectations.json`：`8b6a3ef2d76c089b75933922e57f56a17fcf7fd0c02c5fb1fb15ab5ef3c6c69b`
- `.tmp/engine-audit-20261008/treatment-consultation/observed-results.json`：`a45d582ffb72337c872811b36b0bb4ba2b3b2637a3292f0da195cbe5cb640528`
- `.tmp/engine-audit-20261008/treatment-consultation/extension-results.json`：`f5eac7545b2a92ae19baeb952a8039b51738642f3a07c4bbc624a202cf67643b`
- `.tmp/engine-audit-20261008/treatment-consultation/048-results.json`：`84342605c8236137d9ef1267e8657d3610b5ba53f74482e6f35dbc22d0da2cee`
- `.tmp/engine-audit-20261008/treatment-consultation/offline_probe.py`：`fd0220ee5d4f8138c2765bd694573dcf58484747a95a4050a3f05fe0444686da`
- `.tmp/engine-audit-20261008/treatment-consultation/extension_probe.py`：`84890ce5ba5b1ad04671e5c21582192f156571953cea120561b88620cf94e129`
- `.tmp/engine-audit-20261008/treatment-consultation/048_probe.py`：`3bdfab8ea4f120f3942f5bf0a830c68aa35e51de47873bf7d6c022927056b3e2`

已有公开验收结论文档按当前字节记录SHA：

- `apps/medqc-web/docs/acceptance/2026-09-06-lx0609-transfusion-family-convergence.md`：`0a3b370313002b0b7cbb021c5ee0103e904456792bbfa1cadb83eac3b4aa46cf`
- `apps/medqc-web/docs/acceptance/2026-10-08-isolated-qc-integration.md`：`502a7a9c27eebc3d3af683c113d03c5a06d1fc6cee81e70bcb62c67147e84e83`
- `apps/medqc-web/docs/acceptance/2026-10-08-parallel-repair-real-validation.md`：`713963818dfc687128514e827134d056a88e4199549c87ca64dc3e53ec4c4605`

**这不等于已核对真实脱敏验收输入SHA。** 当前未取得范围匹配的脱敏输入、独立冻结临床预期及其预期SHA的可核对manifest。公开记录仅索引`private`患者材料，本组未读取或哈希这些材料。完整源码哈希、每条规则分类、原观察和限制见同名JSON。

关键生产文件：`apps/medqc-web/backend/app/services/luxian_0609/native_transfusion_execution.py`、`apps/medqc-web/backend/app/services/luxian_0609/native_extended_document_execution.py`、`apps/medqc-web/backend/app/services/luxian_0609/transfusion_result_mapping.py`及`apps/medqc-web/backend/app/data/luxian_0609_rule_master_v1.json`。独占探针目录：`.tmp/engine-audit-20261008/treatment-consultation/`。
