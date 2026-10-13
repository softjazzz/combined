# 2026-10-08 化疗 N13 缺字段事件事实闭环

限定 `LX0609-05-02-01`，工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`。前一 TP-D01 独立提交 `d0f9c829901152a5a9fd7d97bc9916fe076b67cd` 仅补空病程返回的 `None`，本问题不重写剂量匹配。

## 事实修复

旧逻辑只要任意医嘱缺药名、剂量/单位、途径或日期，就跳过全部事件比较，却仅将缺失字段置 unknown，其余字段仍 matched。新逻辑按事件判定字段完整性：缺字段事件不执行比较，贡献受控 `missing_order_event_count`；完整事件继续按原比较器核对。仅缺字段且其余完整事件合规或未能独立关联时为 data_gap；所有无法证明全事件一致的 matched 改 unknown。完整独立事件已经确认的不一致或缺目标药保留 non_compliant，附另一事件真实字段缺口，不因前后顺序丢失。

药名已知但缺其他字段的事件仍参与既有病程片段边界，避免完整事件向不完整事件借同篇剂量。N01/N07 的数值、原单位、分隔、千分位、单位分母算法未修改；TP-D02 的未知他药/动作语义仍未关闭。

## 受控计数合同

旧 `missing_order_fields` 是字段集合，不能表达缺字段事件数；原合同与 unresolved/missing_course/unknown_time 互斥，也不能表达“一个缺字段事件 + 另一完整事件缺口”。必要新增 `missing_order_event_count`，只有新事实带此字段时采用新组合合同；未带新计数的旧事实继续原保护。

新计数必须为 int（bool/float/string/null 拒绝）、非负且不超总医嘱数；与三个已有互斥事件计数合计不超总数。正计数与非空缺字段集合相互对应，禁止携带 matched；全事件缺字段时四字段只能 unknown。允许另一完整独立事件的明确 mismatched 与字段缺口并存并保留 non_compliant；无法独立归属的共享多药片段不确认为缺陷，保留 data_gap。未带新计数的旧事实状态合同不改变。

## 测试与恢复记录

专属测试 `backend/tests/unit/test_luxian_0609_chemo_closure.py` 冻结重建版红例 19 failed / 7 passed，第一次修复后 26 passed，包含5类缺字段和4类完整/不完整事件前后排列、真实正式执行→Binding→Finalizer及隔离SQLite保存新Session回读。最终纠正预期后的专属 40 项加旧 round4、026 关联及 mapping 92 项共 132 passed；显式 round2 化疗节点 27 passed，共 159 项通过，无 deselected。Ruff 三份独占 Python 文件 All checks passed。

首次 TP-D01 提交前，标准 lint-staged 在跨盘工作树的部分暂存路径构造失败，备份失败后将仅本任务未暂存测试恢复为 index；没有他人变更被恢复。按原冻结预期重建测试，SHA256 `786e35af0cc2803ac0e4955e012c3f6d2f2bc3019e0c5f3ba842731159de7dca`，并保存 `.tmp/chemo-closure/n13-frozen-tests.py`。全部测试重新执行，不复用丢失前的记录。后续新增保护只追加案例，不改变原冻结预期。

早期旧保护集 92 passed / 33 deselected；一次 `-k not discharge` 会因模块名把 round2 化疗测试一起排除，不能声称该批已覆盖 round2。最终已使用显式化疗节点 27 项补齐。共享资源发生 PowerShell OOM，降为单测试槽；没有重复运行前端全量，未把资源限制写成通过。

运行器拒绝 `.env*`、模型、真实数据库会话与外部网络；SQLite仅进程内合成数据，Windows asyncio仅内部self-pipe。真实模型/客户PG/正式API/浏览器均未验。TP-D02/03设计见同目录 `2026-10-08-chemo-d02-d03-design.md`，按协调指令本轮不实现其语义分支。

## 错误预期的纠正与客户文案

初版补充预期错误沿用全局“缺字段优先 data_gap”：完整奥沙利铂医嘱与明确120mg病程不一致、或完整未截断病程只记录紫杉醇而缺目标奥沙利铂时，另一顺铂医嘱缺单位不应掩盖独立缺陷。主协调明确裁定统一为 non_compliant，保留已确认的药物/剂量/方法/日期问题，并附另一事件的真实缺口。

已保留 `.tmp/chemo-closure/n13-38-original-gap-expectations.py`，补充纠正预期在 `n13-independent-defect-corrected-expectations.json`，记录原预期 data_gap、纠正为 non_compliant 及独立事件依据。原冻结重建 26 项文件也保留；没有覆盖旧错误预期或冒称初版正确。原合同补充中曾有 3 failed / 35 passed，原因是新组合 sanitize 通过、旧状态优先级拒绝；后来 130 通过的一律 gap 版本经协调审查判定不符合独立缺陷原则，不能作为最终正确语义验收。

最终客户文案使用已有 Renderer，分别写“剂量记录不一致”或“药物名称记录不一致”，并说明其他字段“尚无法核对”；没有声称全批医嘱缺失，不输出“继续保持”。两条不能独立归属的共享多药片段正反序保护仍 data_gap。真实保存器经进程内 SQLite INSERT/commit，关闭写 Session 后由新 Session 的生产 load_selected 回读，核对状态、理由、findings 和精确事实；不访问客户PG。

门禁：前端源码/配置未修改，复用本工作树此前 `npm run lint -- --no-fix` 的 0 errors / 1214 warnings；不重复全量前端。暂存编码及标准 Husky 结果以提交记录为准。类型/前端全量单元受共享资源限制，未报通过。
