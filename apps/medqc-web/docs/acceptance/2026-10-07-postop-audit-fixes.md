# 术后三日病程审计两项缺陷修复

2026-10-07，范围 LX0609-04-05-01（064）。依据独立审计的两个合成反例修复，不变更医学口径或共享时间读取合同。

## 修复

- 有正文的病程无可用日期，且现有定日材料不足以确认该台手术三日覆盖或术者查房时，保留来源证据并返回 `data_gap / required_field_missing`。未知日期不补入覆盖，不把该台未知缺口写入 `unmet_surgery_events`；单独标记 `unresolved_course_time_events`。若有其他台确定缺项与未知候选并存，沿用现有资料不足优先归约。
- 查房标题按职称提取完整身份后相等比较，禁止“李明”匹配“王李明”。受控科室前缀及联合多医师标题保留支持；未知前缀不猜姓名，不新增姓名别名或等价。正文中的术者提及、查房标记后附注均不能证明术者查房。

生产判定改动在 `native_extended_document_execution.py` 的 `_title_round_physician_tokens` 和 064 分支；经主协调授权，另在 `postoperative_result_mapping.py` 保留并严格校验逐事件 `course_time_unresolved` 布尔事实，在 `customer_renderer.py` 的064分支据此说明日期不可用，不再陈述确定缺天。内部事件ID不投影。其他代理正在并发修改同文件的带药分支。新增专属 `backend/tests/unit/test_luxian_0609_postop_audit_regressions.py`。

## 验证

修复前独立审计脚本实际执行：2 failed。分别为所有病程时间缺失误判 `non_compliant`，以及“王李明”误证明“李明”查房。

修复后执行：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_postop_audit_regressions.py .tmp/accuracy-postop-course-private/test_postop_audit_private.py backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -k '064 or postop or title_matches or unavailable_course or time_gap' -q --tb=short -p no:cacheprovider
```

结果：69 passed, 373 deselected。包括26项专属、2项原审计、41项已有术后保护测试。新增正式Aggregator/Finalizer链回归：data_gap状态及安全布尔事实保留，文案不再报确定缺天；4种畸形布尔类型被安全投影拒绝。覆盖全部/部分时间缺失、非法时间、完整日期、明确术前、真正无记录、明确缺日、空正文、额外未知记录、多手术窗口、多医师/职称标题、姓名后缀及含“科”姓名。真实执行器与 Reducer 执行，没有 mock 本次判定逻辑；新时间资料缺口断言 LLM 调用和 token 均为0。

Ruff 检查三个生产文件及专属测试通过；`git diff --check` 通过。未运行全量前端检查或全量后端套件，交由主协调代理执行共同验收。

## 限制

本轮为可复现工程缺陷修复，不宣称客户病例临床准确率或上线验收。原6例真实材料均缺实际手术结束时间，未再读取PG或改写冻结预期；本轮没有真实模型调用、PG写入、服务重启、提交或推送。pytest公共conftest会初始化本地demo SQLite，此输出不代表客户PG写入。

仅提交时间支持覆盖的既有风险未更改，仍需独立业务口径确认。标题解析不承担自由文本姓名识别；未列入受控词表的科室前缀不会被截掉以强行命中术者。
