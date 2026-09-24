# 原始 LX0609-001 已发布事实只读校验

范围：原始 `LX0609-001` 的四段式 ID 为 `LX0609-01-01-01`。权威目录要求入院记录在入院后 24 小时内完成；生产执行器 `native_basic_timeliness.py` 以固定 24 小时生成判定与客户事实。本次只改已发布事实的公开读取，不改医学判据、执行器、证据选择、Prompt 或其他规则。

## 复现与修复

修复前 `canonical_result_finalizer.validate_luxian_0609_published_customer_display_facts` 对 001 回落执行器投影。固定已发布事实为 `timeliness_requirement_satisfied / within / threshold_hours=24 / elapsed_hours=1.0 / remaining_hours=999.0` 时，`safe_customer_display_facts` 将 999 静默改为 23。聚焦红测已复现 `DID NOT RAISE`。现在 001 走专属**公开校验**：合法事实逐字段原样返回；不一致的衍生数值、内部标识、未知键、异常容器、布尔/非有限/负数数值受控拒绝，保留生产投影的两步四舍五入容差。入院时间早于文书时间的冲突分支、空白文书、缺失、迟到、日期锚点和正常分支均有固定输入校验。新公开校验不调用内部投影，也不修改持久化事实。

## 验证与边界

- `test_luxian_0609_basic_timeliness_customer_projection.py` 加 `test_luxian_0609_basic_timeliness_architecture_freeze.py`：83 项通过。冻结例的原始 001 保持 `compliant / requirement_within_threshold`、客户事实 `elapsed_hours=1.0`、相同证据坐标、0 次 LLM 调用。
- `test_luxian_0609_canonical_result_delivery.py` 的相关 SQLite Store/latest/反馈/导出与损坏 JSON 读取：12 项通过。新增 001 的真实隔离 SQLite 写读用例和篡改 `remaining_hours` 后拒绝用例，存储原文不被改写。
- 相关四个 Python 文件 `ruff check` 通过。上述测试只使用固定合成输入、隔离 SQLite 与测试用配置，不访问客户 PostgreSQL 或真实模型。
- 尝试全跑三个文件：121 通过、71 失败；首个失败在无客户配置时的测试用 `DATABASE_URL=sqlite:///unit-test.db` 被应用级 `connect_timeout` 传给 SQLite，报 `TypeError`，未到本次公开事实代码。故不以这次全跑声称全绿；已将适用聚焦项拆开复跑通过。

本闭环只能证明 001 的技术公开合同与固定输入等价，不能证明临床准确率或真实客户数据完整性。主协调另发现基础时限族同次发布的第二次执行器投影调用；它是独立于**公开读取**的发布路径问题，留给下一个受限闭环，不混入本次改动。
