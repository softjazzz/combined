# CT04 无成熟触发且已有讨论资料的NA合同修复

基线195e20cf16402052acb4aff23f76234d144296f4。原CT03冻结T03及专属test_ct04_candidate_prethreshold_existing_discussion_should_remain_not_applicable预期始终为NA，未删除、过滤或改为technical_error。原生执行和Reducer已正确给出not_applicable/trigger_absent_complete，但旧050事实状态合同仅接受空成熟记录列表且discussion_count=0；已有讨论资料count>0因此被公开Finalizer转成technical_error/model_invalid_output。这是原NA裁决被下游误拒，不能证明讨论缺失或已经完成。

本次仅difficult_case_result_mapping的一条谓词：`if not records and discussion_count == 0`改成`if not records`，仍仅接受not_applicable。safe合同已经要求合法入院时间、成熟记录列表、非负整数且非bool discussion_count；因此无成熟触发时讨论资料0/1/多份均保留原NA，discussion_count仍是实际资料行数，不清零、不伪造时间。非空成熟记录仍只允许count0对应NC、正count对应C；CT02缺時和CT03正文gap仍仅data_gap，局部scope仍uncertain；附加gap摘要不允许借此进入NA，原旧kind technical_error兼容不改，额外键仍白名单过滤。

独立冻结12native/15公开合同`F:/MedQC-worktrees/review-artifacts/ct04-closure/expected-v1.json` SHA256 818456501701e3f3088902e647bed7302d5e510ae130ac7fd668f1b10d724505未修改。新专属测试35项对应此矩阵、6非法行数、原文/ID过滤与纯合成SQLite新Engine/新Store回读。初始红10失败/25通过（.tmp/ct04-closure/red.log），全部为真实NA被误拒，无夹具异常。单谓词修复后聚焦260全部通过（.tmp/ct04-closure/green.log，4.24秒）：35CT04、52CT03（含原应NA失败）、56CT02、3mapping、70Finalizer、29RR-PUB、7N12解释支持、6既有native050、2既有renderer050。仅计本次实际完整260，不与其他批次数相加；没有改旧输入/预期求绿。

SQLite正式执行→归约→聚合→保存→新实例回读保留NA/原reason、正资料行数、facts/文案。NA负向适用性结论不产生讨论完成或缺陷文书卡；测试明确断言已读取讨论材料、实际来源快照锚可核、公开evidence=[]，不虚造ID/时间/正文或声称精确卡保存通过。原生模型调用/Token均0；没有PG、env、网络或真实模型，未证明临床语义充分性，CT01/CT-R02继续开放。

源码校验 `.tmp/ct04-closure/frozen-verification.json` 证明只有mapping这一谓词，native、Renderer、Finalizer、公共枚举/Reducer、CT02/CT03/N12测试与074目录合同逐字不变，N12公共tuple保持独立支持提交不夹带改动。1147前端源码/配置hash同本批已完成lint输入，继承lint证据（0错误、1214既有警告）；此前typecheck资源中止、全量前端unit未执行，不宣称通过。新test/mapping进行Ruff与差分校验；提交使用真实Husky及staged编码门禁，临时日志不提交。生产固定后交独审，不代替独审结论。
