# 手术记录逐台覆盖修复

日期：2026-10-07。范围仅 04-02-01、04-02-05，承接 independent-surgery-record-audit 中 SR-01/SR-02；未修改目录、发布范围、模型或业务时限。

## 修复与保守边界

签名回退前核对主表事件与正式记录的受控开始/结束时间、标准化完整术者姓名。不同事件不能共用一份签名记录；同一事件按术式拆行仍可共用文书。主表部分签名缺失不被回退掩盖；全部主表已有合格签名仍保持权威。多台各有可关联签名记录时允许回退。

24小时时限判为病例合规前核对全部合格手术主表行覆盖。无法证明覆盖返回 data_gap / association_failed，不把关联不明当作明确缺文书，也不靠另一规则反推事实。全无记录分支的既有窗口策略未改：窗口未成熟资料不足，明确唯一事件且成熟才判缺失。已确认延迟记录仍保留既有缺陷优先级。

唯一主表/唯一记录且无可比时间的既有回退仍保留；若双方受控时间或术者明确冲突，则不允许回退。同台认定依赖已有结构化身份，不能据本修复宣称真实临床关联均已验收。

## 验证

- 先红灯：两规则 × 第二台同术者/不同术者，共4例正式 session → execute → bind/reduce，修复前均错误 compliant。
- 专属新增20例全部经过正式执行、归约和 Canonical Finalizer，断言状态、原因和0模型调用；含同台拆行、逐台各有记录、时间冲突、未知身份、主表部分签名、完整主表签名、部分覆盖窗口、全无记录成熟窗口。新增003关联缺口展示事实通过现有事实合同，Finalizer显示“单台手术与手术记录的关联信息”。
- 专属20例 + 原执行器104例 + gate freeze 10例：134 passed。Ruff检查两个改动Python文件通过。
- 私有 repro.py / repro_timeliness.py 均退出0：两台一份记录均为 data_gap / association_failed，单台正确记录仍 compliant，跨事件错误记录 data_gap；模型调用均0。
- 额外既有 integration/test_luxian_0609_surgery_gate_entry_regression.py 五例失败：fixture SimpleNamespace 缺 LUXIAN_0609_NATIVE_MDT_040_ENABLED，在 capture_luxian_0609_task_settings 阶段报 AttributeError，尚未到本次执行器。不将该集成套件记为通过，未改共享fixture。

pytest加载项目conftest并初始化本地demo_feedbacks.db；没有模型调用、PG写、服务重启、提交或推送。本轮不包含真实病例临床验收、正式保存/API/浏览器验收。
