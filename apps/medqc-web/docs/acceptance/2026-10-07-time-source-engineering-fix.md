# 2026-10-07 时间来源工程修复

## 已复现与最小修复

- A-TIME-01：首次病程仅有 last_modified_time 或 last_modified_datetime 时，经真实 ETL 别名、正式来源字段投影、证据会话、基本时限执行器与决策归并，错误返回 non_compliant。移除两个最后修改字段到 record_datetime 的别名；保留原生记录、提交、签名时间规则。修复后为 data_gap。
- C-TZ-01：会诊候选时间直接丢弃偏移，同一时刻的 UTC/+05/+08/本地表示会造成住院日边界漏入或漏出，亦可倒置会诊与执行先后。仅修改 native_consultation_episode_execution.\_parse_observed_time 的 ISO 分支，复用 extended_document.shared.\_parse_datetime 已有的 Asia/Shanghai 换算；保留原有斜杠日期和日期精度语义，共享解析源码没有修改。

## 可复核验证

新增 backend/tests/unit/test_luxian_0609_time_source_audit.py，21 项合成保护：两种最后修改字段、原生记录、8 小时恰好与超 1 秒、提交与签名；UTC/Z/+05/+08/naive 等价、入出院跨午夜边界、实际窗口外记录、来源完整性、日期精度与事件先后。

修复前在 C 盘临时测试文件执行相同用例：8 failed, 13 passed；其中两个首次病程用例完整调用上述正式链，会诊用例只替换数据读取，保留生产候选构建及筛选。修复后运行：

```text
python -m pytest tests/unit/test_luxian_0609_time_source_audit.py tests/unit/test_luxian_0609_native_basic_timeliness.py tests/unit/test_luxian_0609_native_consultation_episode_execution.py tests/unit/test_luxian_0609_native_extended_document_execution.py tests/unit/test_luxian_0609_consultation_timeliness.py -q -p no:cacheprovider
854 passed, 15 warnings in 46.41s
```

三个改动 Python 文件 Ruff 检查通过。现有会诊执行测试覆盖解析全部调用者所在执行器；扩展文书及会诊时限也已回归。解析调用范围包括候选行、住院窗口、意见时间、代表文书、事件成员及结果事实时间。测试中的模型客户端为桩；没有真实模型调用。

## 明确边界

首次病程正式 reader 权威字段为 record_time、record_datetime、submit_time、submit_datetime，不直接接纳 last_modified。此次只修后续 ETL 映射。历史已同步 record_datetime 若来自最后修改，来源已丢失，不能自动区分或修复；没有修改 PG、执行迁移或重同步，应另行回源核实。保留提交/签名既有映射不构成对其临床来源语义的新确认。

会诊修复证明候选及时间顺序一致，不证明真实病例最终语义准确率。没有保存/API/浏览器验收、服务重启、提交或推送，不宣称临床验收或历史结果已修。pytest 启动会初始化既有本地测试 SQLite；未发起 PG 业务写入。
