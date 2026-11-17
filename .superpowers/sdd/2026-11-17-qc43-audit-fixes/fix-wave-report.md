# QC43 R1/R2/R3 集中修复记录

基线：`728453b198820a9871b09c1c17c1788b8071e59a`。日期：2026-11-17。分支：`codex/qc43-audit-fixes-20261117`。

## 改动与边界

- R1：`_is_future_discharge_follow_up_clause` 按每个随访动作及标点/转折划分局部作用域，否定可以覆盖专科、疾病、频率等宾语修饰，不再枚举“出院后/门诊”等修饰词白名单；保留后置“计划尚未制定”的否定、并列否定及既往时态保护。独立“但定期复查”可以证明随访计划。
- R2：`_affirmative_discharge_clause` 将否定/计划绑定到紧邻请示、签署动作的情态链，原因中的“不愿继续住院”不再抹去“已请示”；转折分句独立匹配，避免既有请示正则跨过转折吞掉后一个动作。纯历史仍不能证明本次已完成。
- R3：`_is_effective_physician_change_order` 将情态绑定到变更动作，允许“因原医师未到岗现更换经治医师”；取消/作废/撤销/未执行的状态门禁保持原样，纯历史仍被拒绝。结构化事件优先级没有改动。
- 新增 `tests/unit/test_qc43_review_regressions.py`，复用临时复审文件的合成反例和现有测试辅助，包括真实肿瘤执行器/投影、扩展执行器及医师交接判定。R2 的受控替身只用于证明确定性分支无需语义调用，没有真实模型请求。

仅修改上述三个生产函数及必要合成测试/本报告；没有修改配置、接口、原文引用、身份绑定、不可重试处理、历史记录、暂停项、医学阈值、复审报告或主 results 文档。保留工作区原有未跟踪 `docs/superpowers/plans/2026-11-17-qc-stability-effectiveness-closeout.md`，不纳入提交。没有派子代理。

## 验证证据

复用 `final-review.md` 已记录的 RED：临时文件 `C:/Users/Coldplay/AppData/Local/Temp/test_qc43_final_review_synthetic.py` 首轮 4 失败/1 通过，R2 执行器追加例 1 失败；不为重复取得 RED 重跑原集合。

以下所有测试命令的工作目录为 `apps/medqc-web/backend`。离线入口禁 dotenv、网络、非 SQLite 连接；这些用例没有数据库读写。入口创建未连接的内存 SQLite engine，仅为旧导入绑定会话工厂。

### 首次定向回归

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py tests/unit/test_qc43_shared_extraction_failures.py::test_follow_up_plan_rejects_denial_and_history tests/unit/test_qc43_deterministic_regressions.py::test_automatic_discharge_requires_affirmative_consult tests/unit/test_qc43_deterministic_regressions.py::test_cancelled_or_planned_physician_change_is_not_an_actual_event tests/unit/test_qc43_extended_regressions.py::test_discharge_approval_empty_window_body_is_gap tests/unit/test_round2_tumor_dose_discharge_boundaries.py::test_discharge_plan_temporal_scope tests/unit/test_luxian_0609_physician_handoff.py::test_071_explicit_change_with_complete_empty_handoff_is_non_compliant
```

输出：`1 failed, 55 passed, 1 warning in 2.48s`，退出码 1。唯一失败为新增“既往未请示上级医师但本次已请示上级医师”，因既有请示正则跨转折吞掉后一个动作；三项复审原反例已通过。增加函数内转折分句边界后，仅复跑受影响部分：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_action_scope tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_requires_current_signature tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_actual_executor tests/unit/test_qc43_deterministic_regressions.py::test_automatic_discharge_requires_affirmative_consult tests/unit/test_qc43_extended_regressions.py::test_discharge_approval_empty_window_body_is_gap
```

输出：`16 passed, 1 warning in 1.53s`，退出码 0。

### 最终 F3 集合

静态检查删除了“建议”这一不可靠的独立分句边界，避免“取消建议”被误切为肯定。只复跑该函数涉及的集合：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py::test_follow_up_denial_scope tests/unit/test_qc43_shared_extraction_failures.py::test_follow_up_plan_rejects_denial_and_history tests/unit/test_round2_tumor_dose_discharge_boundaries.py::test_discharge_plan_temporal_scope
```

输出：`27 passed, 1 warning in 1.66s`，退出码 0。之后没有再修改 F3 生产代码及其测试。

### 情态保护补查与最终 F4/F6 集合

自查补充“拟行/取消了”紧邻动作的四个保护例，先单独验证：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py -k '\u62df\u884c or \u53d6\u6d88\u4e86'
```

输出：`4 failed, 32 deselected, 1 warning in 1.03s`，退出码 1。请示两例误返 `automatic_discharge`，变更两例误返 `non_compliant`；紧邻动作的情态链遗漏动词“行”和完成助词“了”。补齐后仅复跑改动影响的 F4/F6：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_action_scope tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_requires_current_signature tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_actual_executor tests/unit/test_qc43_review_regressions.py::test_physician_change_action_scope tests/unit/test_qc43_deterministic_regressions.py::test_automatic_discharge_requires_affirmative_consult tests/unit/test_qc43_deterministic_regressions.py::test_cancelled_or_planned_physician_change_is_not_an_actual_event tests/unit/test_qc43_extended_regressions.py::test_discharge_approval_empty_window_body_is_gap tests/unit/test_luxian_0609_physician_handoff.py::test_071_explicit_change_with_complete_empty_handoff_is_non_compliant
```

输出：`33 passed, 1 warning in 1.83s`，退出码 0。与最终 F3 的 27 例不重叠，最终已通过 60 个定向用例；不累加中间重复运行的通过数。

每次运行均输出 `[connection] DATABASE_URL is not configured. Database features are unavailable.`；唯一警告为既有 `app/core/settings.py:59` 的 `PydanticDeprecatedSince20`。

仓库根目录执行 `git diff --check`，退出码 0、无输出。五个交付文本文件逐个按严格 UTF-8 解码，并断言无 BOM、无 CR、以 LF 结尾；通过后本地统一提交。

## 剩余风险与未验证项

局部规则覆盖本次明确反例和直接保护用例，不构成通用中文语义解析器；复杂嵌套、罕见情态/时间插入及跨句指代仍需具体标注反例验证。没有连接 PG、调用真实模型、读取真实临床材料、运行质控任务、测试 API/页面或全量测试。没有擅改复审保留的医学合同争议；这些定向工程结果不能作为 43 项整体医学验收通过的依据。

## 2026-11-17 N1/N2 最后收尾

基线：`340f5614eb21044d440a2f5bb4f81014f18d12ec`。按 `final-rereview.md` 收尾两项新增回归：尚未正式请示不可充当已完成请示，拟明日更换经治医师不可充当实际变更。复用该复核已取得的 `2 failed, 1 warning in 8.77s` RED 证据，不重复执行临时反例文件。

只修改 `_affirmative_discharge_clause` 和 `_is_effective_physician_change_order` 的 `pending_action` 条件及相邻说明，去除情态后的修饰词白名单。情态覆盖任意局部修饰，只有紧邻目标动作的明确“已/已经/现/现已/现行”谓词结束该作用域；“尚未正式”“拟明日”保持未发生，“因患者不愿继续住院已请示”“因原医师未到岗现更换”仍保留实际动作。现有历史判断、状态门禁、结构化优先级及其余生产代码没有改动。两项合成反例加入现有参数集合，未修改 F3 或重跑其集合。

在 `apps/medqc-web/backend` 执行：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_action_scope tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_requires_current_signature tests/unit/test_qc43_review_regressions.py::test_automatic_discharge_actual_executor tests/unit/test_qc43_review_regressions.py::test_physician_change_action_scope tests/unit/test_qc43_deterministic_regressions.py::test_automatic_discharge_requires_affirmative_consult tests/unit/test_qc43_deterministic_regressions.py::test_cancelled_or_planned_physician_change_is_not_an_actual_event tests/unit/test_qc43_extended_regressions.py::test_discharge_approval_empty_window_body_is_gap tests/unit/test_luxian_0609_physician_handoff.py::test_071_explicit_change_with_complete_empty_handoff_is_non_compliant
```

输出：`35 passed, 1 warning in 2.05s`，退出码 0；包括上一波 R2/R3 肯定对照、真实未/拟/取消、纯历史保护和本次 N1/N2。仅既有 `app/core/settings.py:59` 的 Pydantic 弃用警告及数据库未配置提示。没有真实数据、数据库操作、模型请求、质控运行、全量测试或新代理。

根目录 `git diff --check` 无输出、退出码 0；本次四个变更文件的严格 UTF-8 解码、无 BOM、无 CR、LF 结尾检查输出 `UTF-8/no-BOM/LF: 4 files passed`。局部明确完成谓词是有限合同，复杂嵌套和跨句指代仍未验证；不得据此推导真实临床效果或整体医学验收结论。
