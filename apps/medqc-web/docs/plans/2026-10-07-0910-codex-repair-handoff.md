# 0910 准确性验收：交给 Codex 的修复交接（未关闭问题清单）

日期：2026-10-07。交接方：独立验收（Claude）。接收方：Codex（代码修复）。

## 0. 协作约定

- Codex 负责修复；验收方不改生产代码、Prompt、规则目录或发布范围，不改测试预期迁就实现。
- 修复交付须给出**固定提交 SHA** 与修改文件清单。验收方据此：核对 SHA 和范围 → 按原冻结预期复验原反例 → 核对状态、事实、证据、建议及保存/API → 检查同族规则是否被连带改变 → 用未参与修复的病例看泛化（需新增模型调用时先列预算）。复验结论分为：已关闭、部分关闭、未关闭、业务争议、证据不足；工程验收不等于临床批准。
- 私有材料都在 `D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/round-20261007-private/`（下文简称 `$P`），含患者原文，**不提交**。文件哈希见 `$P/ct-real/handoff-file-hashes-private.txt`。凭据只从 `backend/.env` 读取。
- 请避免与验收方同时修改：`docs/acceptance/2026-10-07-0910-*`、`$P/` 下的脚本。
- 基线对照请用隔离工作树；不推送、不重启服务、不改发布范围。
- 当前基线：`1e9af161f5d25c0a0a36513e83a9574c902afa8e`（含 `eea9f38af`、`695000c2a`、`1e9af161f` 三个已提交修复）。

病例别名与真实就诊坐标的映射在 `$P/cases30-counts-private.json`（C01–C30 = 样本池 0910 行号）。

---

## H-01 DR 正侧位被当作 CT/MRI 事件（未关闭，新发现）

- 规则：LX0609-06-01-04、LX0609-06-01-05（同 `exam_lab` 共享抽取，06-01-01/02 可能同样受影响，未验证）。
- 病例/事件：C09 事件 4（07-07 14:37，医嘱“胸椎DR正侧位”）；C10 事件 2（07-07 12:05，医嘱“腰椎DR正侧位”“胸椎DR正侧位(含胶片)”）。
- 运行版本：当前源码 `1e9af161f`（离线 dry-run 构造的送模输入 + 本轮真实调用）；**历史**任务 `e259466c`（2026-09-29，未固定提交）同样把 C10 的 12:05 DR 列为第 2 次检查并判“未完成报告结果记录”。
- 冻结预期：DR/超声等非 CT/MRI 检查不是事件；C09 应为 4 个事件，C10 应为 3 个。依据：规则对象为 CT/MRI 检查（规则目录 06-01-04/05）。预期在本轮任何调用之前冻结，哈希 `7087a189…`（`$P/ct-real/expectations-ct-events-private.json`）。
- 实际：C09 5 个事件、C10 4 个事件；DR 事件在本轮为资料不足，历史版本曾判不合规。
- 对医生的影响：结论里出现“第 N 次 CT/MRI 检查”实为 X 线；在历史版本中曾让一次 X 线被要求补写 CT/MRI 结果记录，可能误报。
- 已确认的责任层：执行器事件投影（`exam_lab_fact_extraction.build_exam_lab_text_projection` 的目标候选判定）。`_IMAGING_CANDIDATE_PATTERN` 对报告正文做 `CT|MRI|磁共振` 文本匹配，DR 报告正文“……请结合CT或MR检查”命中，使该行成为 `EVENT_DOC`。已用当前代码单独验证：该两段 DR 正文匹配为真，普通 DR 正文（无此建议语）匹配为假。
- 未证实的假设：同样的建议语也可能出现在超声报告中；06-01-01/02 是否受影响未验证。
- 最小复现（不调用模型、只读 PG）：
  ```bash
  cd D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/round-20261007-private/ct-real
  PYTHONIOENCODING=utf-8 python ct-real-run-private.py dry C10 C09
  ```
  查看生成的 `C10-dry-private.json`、`C09-dry-private.json` 中 `calls[0].prompt_original` 的 `EVENT_DOC` 标签。环境：本机 PG（`backend/.env`）。
- 材料路径：送模输入与原始响应 `$P/ct-real/C10-real-private.json`、`C09-real-private.json`；抽取事实在其 `calls[0].raw_response`；最终判定与事实在 `decisions`、`customer_display_facts`；生产评价终点快照 `$P/ct-real/record-evaluation-snapshot-from-e259466c-private.json`；回放 `$P/ct-real/ct-replay-private.py`。
- 修复验收条件：C09=4、C10=3、C12=3、C04=4 个 CT/MRI 事件；DR/X 线行不得成为事件，也不得仅凭报告正文的“建议 CT/MR”语句被纳入。
- 必须保持不变（保护样例，用保存的原始响应回放即可）：C12 事件 2 时间冲突→资料不足；C10 07-16 胸椎 CT 仍为不合规（全程未记录）；C04 24.36h、24.3h 两个边界事件仍为不合规；C09、C10 仅提交时间事件仍为资料不足。注意：修复会改变事件数与 `event_position`，原始响应中的事件编号将不再对齐，**原保存响应不能直接回放到修复后版本**，需要新调用（预算另报）或在复验中只核对确定性的事件投影。

## H-02 C04 术前讨论记录“术前准备”引文拼接导致 04-01-05 无法判定（部分关闭）

- 规则：LX0609-04-01-05（与 04-01-04 共享一次抽取）。病例：C04（单台手术，单份讨论记录）。
- 运行版本：真实调用于 `eea9f38af` 执行（2026-10-07，4 次中的 1 次）；`1e9af161f` 离线回放（同一原始响应）。
- 冻结预期：不合规，缺“具体讨论意见”“记录者签名”（批次 1 冻结，形成于查看系统结论之前，`$P/expectations-private.json`，哈希 `f8eb225c…`）。依据：讨论记录无参加人员具体发言，主持人/记录者签名均未出现（`host_name` 为空）。
- 实际：
  - `eea9f38af`：模型把两处不连续原文用 `...` 拼接作为“术前准备”引文，整份共享抽取作废，04-01-04 与 04-01-05 都是资料不足。
  - `1e9af161f`：失败已隔离：04-01-04 恢复为不合规（缺术前诊断、术者术前查看）；04-01-05 资料不足（`preop_fact_extraction_invalid`，失败字段“术前准备”）。
- 为何仅“部分关闭”：失败已如实表达且不再连带 04-01-04，但 04-01-05 仍与冻结预期（不合规）不一致；模型在同一次输出中对“具体讨论意见”(unknown) 与“记录者签名”(missing) 的判断本身与原文相符。
- 已确认的责任层：模型抽取输出不合规（引文非连续原文）；执行器按合同拒绝该字段。
- 未证实的假设：Prompt 对“禁止省略号拼接”的约束不够明确；单字段失败后其余已校验字段能否支持“确认缺项”需要业务确认（见 Q-01）。
- 最小复现（不调用模型）：
  ```bash
  cd D:/LLM/LX888/apps/medqc-web/.tmp/0910-full-audit/round-20261007-private
  PYTHONIOENCODING=utf-8 python real-run-replay-private.py C04
  ```
- 材料：`$P/real-run/C04-real-private.json`（送模输入原文与脱敏版、原始响应、模型配置、事实、判定、调用量）。
- 修复验收条件：在不放宽引文原文校验、不把失败字段改写为 unknown 的前提下，C04 的 04-01-05 达到冻结预期（不合规，确认缺项为具体讨论意见与记录者签名），或在业务确认 Q-01 后按确认口径判定；需要新模型调用时由验收方另列预算，并区分首调与恢复。
- 必须保持不变：C04 的 04-01-04 结果；C02 04-01-05 不合规（缺具体讨论意见）；C09、C10 04-01-05 合规；任何无效引文不得进入公开事实或证据。

## H-03 术前讨论记录不合规时整改建议过度要求（未关闭）

- 规则：LX0609-04-01-05。病例：C02（仅缺“具体讨论意见”）。
- 运行版本：历史 `e259466c` 已出现；当前源码 `1e9af161f` 静态确认仍存在：`customer_renderer.py` 对 04-01-05 不合规使用固定文案“请在同一份术前讨论记录中补齐缺失项目、主持人小结和记录者签名。”，不读取实际缺项。
- 冻结预期：建议只要求补实际缺失项目（C02 只缺具体讨论意见）。
- 对医生的影响：会被要求补写已存在的主持人小结和签名。
- 责任层：Renderer（文案）。执行器事实中 `missing_fields` 已正确。
- 验收条件：04-01-05 不合规时，结论与建议只列执行器确认的缺项；C02、C04 各自的缺项文字正确；04-01-04 文案不变。
- 同一问题的证据侧（批次 1 P5）：04-01-05 的公开证据只有文书标题、C04 摘录为空，不支持“内容完整/缺具体意见”的结论。当前源码未复验，属**证据不足**，请一并核查证据选择。

## H-04 非 +08 偏移时间被静默忽略（未关闭，潜在，单独登记）

- 位置：`exam_lab_fact_extraction._parse_datetime` 对非 +08:00 的带偏移时间返回空，不换算。0910 主表报告时间（UTC，`+00`）175/175 被忽略，由明细报告时间兜底，样本中尚未造成错误。
- 若修复：须同时处理 1/175 行主表与明细相差约一天的来源冲突（启用换算后该事件会转为时间冲突）。修复前请先确认范围，避免与基础时限族的已有时区修复重复。

---

## 需要用户确认的业务问题（不交 Codex 直接修）

- **Q-01（关联 H-02）**：讨论记录某一字段引文不合格时，其余已校验字段确认的缺项能否据以判“不合规”？若可以，需定义字段级失败的展示方式；若不可以，H-02 的现状（资料不足）即为正确结果。
- **Q-02**：术前小结计划术式与实施术式范围不同（C04 楔形切除→肺叶切除，术中扩大）是否视为同一台手术的小结。现状：保守地无法归属并列待确认。
- **Q-03**：CT/MRI 阳性结果“仅列示未分析”是否算已分析（C05、C06、C12 胸/头 CT 的钙化、渗出、结节等）。现状按事实区分，口径未定。
- **Q-04**：06-01-01 医嘱与病程一致性在 0910 上 8/10 资料不足（医嘱全名逐字匹配 + `exam_time` 全空）。需确认检查名称等价与日期锚来源后才宜修改。

## 已关闭（供参考，不需处理）

- 术前小结“确认缺少”含已存在内容 → `eea9f38af` 修复，真实输出与回放验证。
- 术式引文标签残留导致关联失败（C02、C09、C10）→ `695000c2a`，真实响应回放验证。
- C12 时间冲突、C09/C10 仅提交时间、C04 24 小时边界 → 本轮真实调用（`1e9af161f`）验证与冻结预期一致（见第六轮报告）。

## 仍未覆盖

重复运行稳定性；CT/MRI 客户文案经 Finalizer→保存→API 的完整链路；06-01-01/02 在 H-01 下的影响；未参与修复的泛化病例。

---

# 第二轮交接（复验 `6fc7bcfde` 后，2026-10-07）

复验报告：`docs/acceptance/2026-10-07-0910-h01-h03-recheck.md`。复验私有材料：`$P/h01-recheck/`，哈希见 `$P/h01-recheck/recheck-file-hashes-private.txt`。状态更新：H-01 原反例已关闭、整体部分关闭；H-03 文案已关闭、证据未关闭（下称 H-03b）；H-02、H-04 不变。

## R-01 CT 引导操作的引导事件识别回归（未关闭，`6fc7bcfde` 引入）

- 规则：LX0609-06-01-02/04/05（共享事件投影）。病例：合成保护用例（`tests/unit/test_luxian_0609_guidance_event_execution.py`，来自既有修复 `dadbb71d9`）；0910 真实数据未触发（相关主记录均有执行科室）。
- 运行版本：`6fc7bcfde` 失败 6/11；隔离基线 `607623815` 通过 11/11。
- 冻结预期（即该文件既有断言，形成于本修复之前）：主记录无身份、报告正文“CT引导下操作”的纯引导事件仍为已确认影像事件且 `guidance_only=True`，文书顺序为 `("E02-01","E01-01")`；纯引导时 06-01-04/05 不调用模型直接不适用；混合事件保留诊断事件事实。
- 实际：事件未确认、顺序变为 `("E01-01","E02-01")`、引导标记丢失；纯引导路径开始调用模型（替身客户端 `StopIteration`），并出现 `ExamLabFactParseError`。
- 对医生的影响：纯 CT 引导操作可能被当作需记录/分析结果的诊断影像，或产生不必要的模型调用与资料不足。
- 已确认责任层：执行器事件投影——`build_exam_lab_text_projection` 的候选判定改为只看身份字段/执行科室后，不再识别正文对**本次检查**的描述（“CT引导下操作”），与“建议 CT/MR”“与 CT 比较”等非本次检查语句未作区分。
- 未证实假设：正确做法可能是区分“本次操作/检查的自述”与“建议/比较”，或改由医嘱名称确认；请 Codex 判断，不得通过修改该测试预期迁就实现。
- 最小复现：
  ```bash
  cd D:/LLM/LX888/apps/medqc-web/backend
  python -m pytest -q -p no:cacheprovider tests/unit/test_luxian_0609_guidance_event_execution.py
  ```
- 验收条件：该文件 11/11 通过且未修改既有断言；H-01 的 C09/C10 DR 反例仍不成为事件；`$P/h01-recheck/projection-dump-private.py` 对 30 例投影与 `proj-fix-private.json` 中除 R-01/R-02 涉及行外一致，62 个真实 CT/MRI 主记录仍全部确认。
- 保护样例：C09=4、C10=3、C12=3、C04=4 事件（按检查号）；C21/C28/C30 未确认通用事件不变；C28 仍不调用模型直接不适用。

## R-02 主表与明细身份冲突时被确认为 CT（未关闭，边界缺陷）

- 规则：同 R-01。病例：合成边界探针（`$P/h01-recheck/edge-probes-private.txt` 情形 5、7）；0910 未出现。
- 运行版本：`6fc7bcfde`。
- 冻结预期：主表（科室 CT室或名称“胸部CT”）与明细（名称“胸部DR”）类型冲突时，不得直接确认为 CT/MRI 事件，应作为冲突/待确认处理（不判“无检查”，也不判“确定适用”）。依据：H-01 的修复目标“以结构化身份确认类型”；冲突身份不能确认类型。说明：该口径来自用户在本轮验收任务中提出的检查要求（“主从信息冲突不得被错误判成确定适用”），我没有在运行探针前单独冻结成文件，按如实记录处理。
- 实际：事件 `target_confirmed=True`。
- 责任层：执行器事件投影（逐行候选判定后按业务键合并，未检查同一业务键内身份冲突）。
- 最小复现：见复验报告第 1 节表格；脚本内容为直接调用 `build_exam_lab_text_projection` 的 10 个合成情形，输出存于 `$P/h01-recheck/edge-probes-private.txt`。
- 验收条件：情形 5、7 不再为已确认事件；情形 3、9、10 保持已确认；情形 1、2、4、6、8 保持未确认；R-01 用例全通过。

## H-03b 术前讨论记录公开证据只有标题或为空（未关闭）

- 规则：LX0609-04-01-05。病例：C02（不合规）、C09（合规）证据仅文书标题“术前讨论记录”；C04（资料不足）证据摘录为空。
- 运行版本：`6fc7bcfde`，真实原始响应离线回放→正式 binding/归约→正式 Finalizer（`$P/h01-recheck/preop-finalize-private.py`，输出 `preop-finalized-items-private.json`）。
- 冻结预期：公开证据应能让医生核对结论——不合规时指向确认缺项所在文书的相关结构化内容或说明该项缺失的核对范围；合规时指向支持完整的内容；不得引用模型引文。
- 实际：讨论记录正文 `record_content` 为空，内容在 `discuss_staff`、`host_summary` 等结构化字段；证据摘录按字段顺序取到 `document_title` 或空。
- 责任层：公开证据投影（`customer_evidence_enrichment` 的摘录字段选择）；执行器事实本身正确。
- 验收条件：C02、C09 的证据摘录来自讨论记录实际结构化内容；C04 资料不足时不得引用不合格引文；04-01-04 证据不变；保存/API 合同不放宽。
- 保护样例：C02 结论与建议仅列“具体讨论意见”；C04 04-01-05 仍为资料不足；任何模型引文不得进入公开证据。

---

# 第三轮交接（复验 `64dd69e9a`、`fbf9c28` 后，2026-10-07）

复验报告：`docs/acceptance/2026-10-07-0910-r01-r02-h03b-recheck.md`；私有材料：`$P/r01-r02-h03b-recheck/`。状态更新：R-01 已关闭、R-02 已关闭、H-03b 已关闭（按交接验收条件）；H-02、H-04、Q-01～Q-04 不变。

## R-03 讨论记录证据：预设字段坐标不存在时被填入另一字段内容（未关闭，潜在）

- 规则：讨论记录证据补齐（04-01-05 及其他引用 `presurg_discussion` 证据的规则）。
- 运行版本：`fbf9c28`（隔离工作树）。
- 冻结预期：用户在本轮任务中明确要求“明确指定的字段不存在或匹配不唯一时，不得偷换成另一字段”。
- 实际：证据行事先带 `field_path=discuss_staff`，而该讨论记录只有 `host_summary`；补齐后 `field_path` 仍为 `discuss_staff`，`evidence_excerpt` 却是 `host_summary` 的内容，`excerpt_kind=字段级依据`。latest 读取时因该字段不存在返回空、不覆盖，因此错配会被保留。
- 可达性：正式 Finalizer 不为讨论记录预设字段坐标，本轮真实链路未触发；兼容/旧结果适配路径是否会带入预设坐标未验证。
- 责任层：`customer_evidence_enrichment.enrich_customer_evidence`（已有 `field_path` 时仍用 `_discussion_excerpt` 的首个有内容字段填充摘录）。
- 最小复现：`$P/r01-r02-h03b-recheck/h03b-probes-private.py` 情形 E（直接调用补齐、组装与授权摘录函数，不读库）。
- 验收条件：预设字段存在时摘录来自该字段；不存在或不唯一时不填摘录（或明确标注为缺失），不得改用其他字段；情形 A、B、G 结果不变；04-01-03 偏好字段既有行为单独说明。
- 保护样例：C02/C04/C09/C10 的 `host_summary` 摘录与本轮回放结果一致；无 `repr`；模板章节不得成为证据。

## 仍需用户或后续轮次决定

- 06-01-01、06-01-03 由 `handbook_exam_lab` 按名称建事件，不经过本次修复；是否存在同类主从身份冲突未验证。
- C09、C10 在修复后的模型输入已变化，需新模型调用才能验证其输出；计划与预算见复验报告第 7 节。

---

# 第四轮交接（复验 `88aa13770`、`d081b3dca` 后，2026-10-07）

复验报告：`docs/acceptance/2026-10-07-round2-d081-independent-recheck.md`；私有材料：`$P/round2-recheck-88aa/`（`$P` = `.tmp/0910-full-audit/round-20261007-private`）。探针脚本均以环境变量 `ACC_BACKEND` 指向某一工作树的 `apps/medqc-web/backend`，同一输入可在不同 SHA 对比；模型调用 0。状态：N-01 已关闭；R-03、H-02、H-04、Q-01～Q-04 不变；第 4–6 项未复验。

## N-05 抗菌药取消状态吞掉明确给药（阻断，新回退）

- 固定 SHA：`d081b3dca`（`88aa13770` 引入）。规则：LX0609-05-01-03、05-01-06（05 同函数）。
- 输入（合成）：美罗培南医嘱 `order_status=已取消`；同一医嘱病程写“已予美罗培南静滴抗感染。”（03，daily）或“给予美罗培南抗感染治疗。”（06，senior）。
- 冻结预期：明确实际给药与取消状态冲突时，不得以“从未给药”排除（修复文档自述同一合同）。
- 实际：`not_applicable / trigger_absent_complete`；基线 `57b863d2b` 为 `non_compliant`。
- 责任函数：`native_extended_document_execution._exclude_unperformed_antimicrobial_orders`。“已实施”只认“已给予/已使用/已启用/已输注/实际给予/实际使用”，取消状态即排除。
- 复现：`ACC_BACKEND=C:/wd08/apps/medqc-web/backend python -X utf8 $P/round2-recheck-88aa/semantic-probe-private.py`，看 `AM3b`、`AM3c`。
- 正常对照：已取消且“未实际给药/患者拒绝未给药”→不适用；已取消但“已使用…1剂”→仍计实际用药；已停止→仍计实际用药。
- 证据层级：合成、正式执行器→归约；真实病例未观察（修复文档称六例真实源无取消状态）。
- 建议最小修复边界：取消排除只在无任何肯定给药叙述时生效；肯定给药识别至少覆盖“已予/予以/给予…静滴/输注”等实际给药表述，有冲突时保留医嘱（或资料不足）；保留上述对照。取消码表仍需医院确认。

## N-04 麻醉访视带前缀空标题仍计已填写（未关闭，原 D1 修复不完整）

- 固定 SHA：`d081b3dca`。规则：LX0609-04-04-02。
- 输入（合成，其余完整）：术前“既往麻醉史：”、去掉结构化签名后正文“麻醉医师签名：”、术后“术后并发症：”“术后意识：”“呼吸系统：”（各自单独替换）。
- 冻结预期：空字段不得计为已填写，应不合规并列出对应字段。
- 实际：均 `compliant`（基线同）。原因：`_row_has_any` 去掉 marker 后，剩余前缀（既往/麻醉/术后/系统）不在模板词表，被当成有值。
- 复现：`ACC_BACKEND=C:/wd08/apps/medqc-web/backend python -X utf8 $P/round2-recheck-88aa/anesthesia-probe-private.py`，看 `AN5a–AN5f`（`AN5e` 为已修好的“ASA分级：”）。
- 正常对照：AN1 完整、AN6 有效阴性、AN6b“ASA分级：Ⅱ级”合规。
- 建议最小修复边界：判断“标签冒号后是否有值”，不枚举前缀词；保留有效阴性。真实源无麻醉访视行，未观察。

## N-03 化疗核对资料不足时公开文案声称“剂量一致”（未关闭，既有）

- 固定 SHA：`d081b3dca`（`57b863d2b` 已存在于医嘱缺剂量场景；缺单位进入资料不足后更易触达）。规则：LX0609-05-02-01。
- 输入：医嘱缺单位或缺剂量，病程“使用奥沙利铂130mg 静滴”。
- 实际：`data_gap / required_field_missing`，`field_results.dose=unknown`，但 findings 为“已核对 1 条化疗医嘱及对应病程，药物名称、剂量、使用方法和用药时间一致。”
- 冻结预期：资料不足不得声称已核对一致（用户本轮明确“不能声称已核对单位”）。
- 责任函数：`customer_renderer.py` 中 `LX0609-05-02-01 / chemotherapy_order_course_comparison` 分支，只区分 `mismatched`，忽略 `unknown`。时间未知、事件关联不唯一等资料不足终态同理（未逐一跑）。
- 复现：`ACC_BACKEND=C:/wd08/apps/medqc-web/backend python -X utf8 $P/round2-recheck-88aa/dose-findings-private.py`。
- 正常对照：完整医嘱合规时该文案正确。

## N-02 剂量前紧邻“数字+逗号”被当千分位（未关闭，低，新回退）

- 固定 SHA：`d081b3dca`。规则：LX0609-05-02-01。
- 输入：病程“d1，130mg”“d1,130mg”“体表面积1.7，130mg”，医嘱 130mg。
- 实际：`non_compliant`（88aa 为合规）。责任函数：`_chemotherapy_dose_matches`。全角逗号被当千分位，且 `(?<!\d,)(?<!\d，)` 拒绝紧随“数字+逗号”的剂量。
- 复现：`ACC_BACKEND=C:/wd08/apps/medqc-web/backend python -X utf8 $P/round2-recheck-88aa/dose-supplement-private.py`，看 S11、S12、S14。
- 正常对照：1,130mg 仍不得匹配 130mg（S10）。0910 30 例真实源未见此写法。
- 建议边界：全角逗号不作千分位；千分位只在逗号后恰好三位且前段不是 d1 一类日程标记时成立。不能确定时宁可资料不足，不判不一致。

## N-06 病理取材：单事件正常材料收紧为资料不足（未关闭 / 口径待定）

- 固定 SHA：`d081b3dca`（`88aa13770` 引入）。规则：LX0609-06-02-02。
- 输入（合成，单申请、单报告、单手术）：(a) 手术日早于病理申请日；(b) 标本为“手术标本”泛称；(c) 申请无时间；(d) 旧夹具形态去掉注入的“病理号”。
- 实际：均 `data_gap / association_failed`；基线合规。06-02-03 同输入保持合规。
- 判定：(a) 的“取材记录日期须不早于申请日”没有业务依据，真实源 C01 存在手术日早于申请日，列**工程收紧未关闭**；(b)(c) 单事件能否视为同次关联属**业务口径待定**；(d) 说明旧夹具注入真实数据中不存在的“病理号”（真实源 0/20），掩盖了行为变化，建议改为显式测试资料不足行为。
- 复现：`ACC_BACKEND=C:/wd08/apps/medqc-web/backend python -X utf8 $P/round2-recheck-88aa/pathology-probe-private.py`，看 PN2、PN3、PN4、PN7。
- 正常对照：PN1、PN1b、PN6、PN8 合规；跨事件原反例 PA1–PA6 资料不足。真实 6 例因最终诊断门控先退出，未实际触达。

## 待 N-05 修复后的复验

第 4–6 项和宽范围串行回归按既有冻结预期执行；随后再申请 C09/C10/C05 真实模型调用（硬上限 6 次），未授权前不执行。

---

# 第五轮交接（复验 `1f9f7f703` 后，2026-10-07）

复验报告：`docs/acceptance/2026-10-07-round5-1f9-independent-recheck.md`；探针均在 `$P/round2-recheck-88aa/`，以 `ACC_BACKEND=C:/<工作树>/apps/medqc-web/backend` 指定版本，模型调用 0。已关闭：N-02、N-03、N-04（原反例）、N-05、N-06 的取材早于申请子项、016、R-03、065/067 冻结项、008/009 跨时重开。仍需 Codex 修复的最小清单如下。

## N-07 剂量前紧邻字母被拒（新回退，1f9 引入）

- rule_id：LX0609-05-02-01。函数：`native_tumor_pathology_execution._chemotherapy_dose_matches`。新增的 `(?<![a-z\d.+-])`（IGNORECASE）拒绝任何紧跟字母的剂量数字。
- 输入：医嘱奥沙利铂 130mg；病程 `奥沙利铂(FOLFOX) L-OHP130mg 静滴`、`奥沙利铂Oxaliplatin130mg`、`ivgtt130mg`。冻结预期：合规。实际：不合规（d081 为合规）。
- 复现：`python -X utf8 $P/round2-recheck-88aa/dose-letter-private.py`（X01–X03）。正常对照：X05 `L-OHP 130mg` 合规；S14 `d1,130mg` 合规。
- 修复边界：只排除"日程标记 d/D + 数字 + 逗号"这一类前缀被并入千分位，不要一律拒绝字母后的数字；保留 N-02 全部 46 例及 X 系列。

## N-08 未知空标签紧贴已填值误伤前一字段（新回退，低）

- rule_id：LX0609-04-04-02。函数：`native_surgery_document_execution._row_has_any`。
- 输入：术后"神志清醒心率：；呼吸平稳；循环稳定；无麻醉并发症。"冻结预期：合规。实际：不合规，判缺 consciousness_status（d081 为合规）。
- 复现：`python -X utf8 $P/round2-recheck-88aa/anesthesia-multifield-private.py`（M06）。正常对照：M06b/c/d（加空格、逗号或填值）合规；M01–M05 保持。
- 修复边界：空标签判定只作用于该标签自身，不让紧随的未知空标签使前面已填值失效。

## N-11 化疗关联不唯一变 technical_error 且无法保存（确认残留，d081 已存在）

- rule_id：LX0609-05-02-01。Owner：执行器 `_typed_chemotherapy_comparison`；连带 `tumor_pathology_result_mapping._safe_026` 和 `tumor_pathology_customer_fact_status_is_valid`。
- 输入：一条 130mg 医嘱，两份同日同剂量病程。冻结预期：交付 data_gap，不声称一致。
- 实际：执行器 field_results 全 matched + unresolved_event_count=1，归约 data_gap；映射丢弃 unresolved_event_count；状态校验要求合规；Finalizer 输出 technical_error / model_invalid_output，findings 为空；`replace_for_job` 抛"Canonical Envelope 状态字段不一致，拒绝完成质控任务"。
- 复现：`python -X utf8 $P/round2-recheck-88aa/chemo-assoc-private.py`（K01；K03 为正常对照）；仓库严格 xfail：`tests/unit/test_round4_chemo_dose_and_findings.py::test_ambiguous_association_does_not_claim_initialized_fields_are_verified`。
- 修复边界：执行器不得把未关联事件的字段报为 matched，应标为 unknown（或增加受控关联缺口事实并扩映射白名单）；不放宽"全 matched 只能合规"的校验。保护：K01 交付 data_gap 且文案不写"一致"；单病程合规；"一不一致 + 一未关联"不得变成 technical_error，也不得丢失"不一致"。

## N-09 同一分钟解除与重开丢失重开区间（确认残留）

- rule_id：LX0609-02-01-04/05。函数：`course_quality/rules_008_009._severity_active_date_intervals`。同一时间点开始事件排在解除之前，重开被忽略，解除又关闭了区间。
- 输入：08:00 开、10:00 解除、10:00 重开，仅 1/1 有病程，终点 1/7。实际：合规（两种行顺序均如此）。冻结预期：不得静默丢弃重开后判合规。
- 复现：`python -X utf8 $P/round2-recheck-88aa/severity-probe-private.py`（RC5/RC5b）。正常对照：RC4 15:00 重开判不合规；解除后不重开判合规。
- 修复边界：同一时刻出现解除与开始、无法证明先后时，返回资料不足或保守保留重开，不按 kind 排序擅定顺序。

## N-10 模板标题当作有效病程/查房正文（确认残留，低）

- rule_id：LX0609-04-05-02（065）、LX0609-08-02-01（067）。函数：`extended_document/discharge_course._has_course_body`。
- 输入：正文"查房记录：\n医生签名：张医生"，或仅"主任医师查房记录"。实际：合规（基线同）。依据：用户要求"空白模板不能算有效病程"；该输入在冻结后补充。
- 复现：`python -X utf8 $P/round2-recheck-88aa/rounds065-067-private.py`（RC7c/RC7d/RC9b）。正常对照：RC8/RC8b/RC10 合规。
- 修复边界：只把"标题行 + 签名行"的纯模板排除，不评价正文长短。

## 口径待定（需用户决定，不交 Codex 自行判断）

N-06 泛称标本 / 申请缺时间；麻醉记录时间只有日期；016 全角与半角标点差异；"并发症：/" 占位符；PA5 业务键冲突下 06-02-03 合规。

---

# 第六轮交接（复验 `83afaf4d3` 后，2026-10-07）

复验报告：`docs/acceptance/2026-10-07-round6-83a-independent-recheck.md`。已关闭：N07、N09；N08、N10、N11 部分关闭；074 工程加固通过，真实模型未验证。探针以 `ACC_BACKEND=C:/<工作树>/apps/medqc-web/backend` 指定版本，位于 `$P/round2-recheck-88aa/`，模型调用 0。

## N-12 麻醉“前缀+后缀”空标签被当作已填写（新回退，058c2d2ad 引入）

- rule_id：LX0609-04-04-02。函数：`native_surgery_document_execution._row_has_any`。N08 修复去掉了通用的“marker…冒号后为空”否定，只认已知标签表里的空标签。
- 输入（其余字段完整）：术后“术后意识状态：”“术后呼吸情况：”“术后并发症情况：”；术前“Mallampati气道分级：”。冻结预期：对应字段缺失、判不合规。实际：判合规；`1f9` 为不合规。
- 复现：`python -X utf8 $P/round2-recheck-88aa/anesthesia-l-private.py`（L01–L04；L05/L06 为 N08 正常对照）。
- 正常对照：M06“神志清醒心率：”合规；AN5 系列、M01–M05、有效阴性保持。
- 修复边界：对含 marker 的标签判断“标签自身冒号后是否为空”，前后附加词不限于已知表；不得让后续未知空标签抹掉前一字段已填的值。

## N-13 医嘱缺单位/剂量时未比较字段仍报 matched（残留，基线已有）

- rule_id：LX0609-05-02-01。函数：`_typed_chemotherapy_comparison`（`missing_order_fields` 非空时整体跳过比较），合同 `_safe_026` 接受。
- 输入：医嘱缺单位（或缺剂量），病程同日同剂量。实际：资料不足，`field_results` 为 drug_name/route/time=matched、dose=unknown，并经保存。冻结预期：未比较字段不得报 matched。
- 复现：`python -X utf8 $P/round2-recheck-88aa/n11-chain-private.py`（K06），合同探针 `missing_order_fields_with_matched`。
- 修复边界：跳过比较时其余字段标 unknown（或单独比较可比字段）；合同拒绝“缺医嘱字段 + matched”。保护：K01/K02b/K04/K05 六排列及正常 K07。

## N-10 残留：带日期/姓名前缀的标题行仍计为正文（低，基线已有）

- 输入：“2026-07-02 09:00 主任医师查房记录\n医生签名：张三”，或“张三主任医师查房记录”。实际：065、067 均判合规。复现：`template-b-private.py`（B01/B02）。0910 真实源中未见这两种首行写法。

## 074 真实模型复验计划（待用户批准，未执行）

- 模型/服务：alibaba DashScope `qwen3.8-flash`，thinking 开、预算 256，temperature 0.2，max_completion 2048，无长度重试、无传输重试，不写 PG（NullLLMCallEventStore）。
- 调用：最多 2 次，C20 一次、C07 一次，失败不重试。
- 预计 Token：输入约 1,750（C20）+ 1,430（C07）≈ 3,200；输出通常 400–700/次，上限约 2×2,304。
- 观察点：C20 的引文是否逐字保留中文引号，依据是否为单段连续、含检查依据的片段；无效引文仍须被拒。
- 隐私：送模内容为病程正文，不含患者姓名、住院号或病案号；含年龄、性别、病情及医师签名姓名。原文、输入、响应只存私有目录。
