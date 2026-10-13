# N-05 取消状态与实际抗菌给药冲突修复

2026-10-07；修复前共享 HEAD `fa5fb788f26c2d29bd39f66fcde34eda807a6981`。本轮仅本地未提交修改，无真实模型、PG 访问/写入、正式任务或重启。

## 缺陷和首次引入

规则 LX0609-05-01-03/05/06 共用取消事件过滤。独立复验的 AM3b（已取消，同医嘱“给予美罗培南抗感染治疗”）及 AM3c（已取消，同医嘱“已予美罗培南静滴抗感染”）被静默判不适用。新增测试从正式证据快照进入执行器、绑定归约、aggregate/Finalizer，修复前两例均得到 `not_applicable`，期待 `non_compliant`，2 failed。

`git log -S '明确已实施与取消信息冲突'` 与该提交 diff 定位首次引入为 `88aa13770ad4e688f99e48c6c0293988889502c0`（修复第二轮质控审查缺陷并补齐证据与文书边界）。该提交新增取消过滤，实际给药的正则仅包含已给予/已使用等，漏掉给予、已予。独立探针保持显式 related_order_id 不变，分别输入已给予/给予/已予，保留数依次为 1/0/0，排除关联失败假说。

## 最小改动及边界

生产文件：`backend/app/services/luxian_0609/native_extended_document_execution.py`，新增 `_has_performed_antimicrobial_administration` 并在 `_exclude_unperformed_antimicrobial_orders` 的 performed 判断处调用。

补识别已予、给予、予以、已予以目标药的明确给药表达，按分句检查否定、计划和历史前缀；使用既有药名识别，避免已使用另一药被归给已取消的目标药。不新增药物目录，不猜数值状态码，不改变医嘱关联与取消状态集合。取消冲突时只保留事件，合规、缺项或资料不足仍由原规则计算，不统一强制不合规。

专用新增测试：`backend/tests/unit/test_luxian_0609_antimicrobial_cancel_conflict.py`（52 项，全部正式执行器→归约→Finalizer，llm_client=None 且调用数断言为 0）。测试包含 AM3b/c 原文、予以静滴/输注、已予以；取消未执行、未/拟予以、未曾给予、计划与实际分句、考虑感染已予、同/分句其他药给药，以及经验性治疗理由充分时仍合规。未编辑 Renderer 或其他 owner 文件。

## 红绿验证

1. `python -m pytest backend/tests/unit/test_luxian_0609_antimicrobial_cancel_conflict.py -q --tb=short`：初始仅 AM3b/c，**2 failed**，实际均错误不适用。
2. 初版修复后专用+原抗菌回归：44 passed。协调复核补齐予以及异药边界，再执行专用 `-k yuyi`：**6 failed、2 passed**；红项为3个予以实际给药、未曾给予及2个异药串用。
3. 最终：`python -m pytest backend/tests/unit/test_luxian_0609_antimicrobial_cancel_conflict.py backend/tests/unit/test_luxian_0609_antimicrobial_audit_regressions.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q -k 'antimicrobial or am3b or current_infection or cancelled_plan or plan_clause or actual_empiric or yuyi' --tb=short`：**127 passed、355 deselected**，约2.13秒测试时间。专用52、原抗菌16、native定向59。
4. `python -m ruff check backend/app/services/luxian_0609/native_extended_document_execution.py backend/tests/unit/test_luxian_0609_antimicrobial_cancel_conflict.py`：All checks passed。
5. `git diff --check -- backend/app/services/luxian_0609/native_extended_document_execution.py backend/tests/unit/test_luxian_0609_antimicrobial_cancel_conflict.py`：通过。

测试启动既有 conftest 会加载应用并提示本地 demo_feedbacks.db 初始化；未启动服务或调用模型，未访问客户 PG。现有依赖弃用警告15条，没有测试失败。

## 未覆盖与保留事项

这是合成工程回归，不是0910真实病例准确率或临床验收。医院取消数值码表仍未知；多医嘱归属不明保持既有保守关联。未尝试覆盖任意复杂自然语言、长距离指代或计划/否定所有语言变体。已有“未行培养”“排除感染”等其他理由识别问题不在本轮修复；未改医学口径、目录、默认启用范围。未跑全量后端/前端、浏览器、客户存储或正式任务。
