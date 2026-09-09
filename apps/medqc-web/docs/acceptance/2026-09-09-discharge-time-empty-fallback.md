# 出院日期为空时补取业务出院时间

## 问题与最小方案

原排障包中，登记与病案首页的 discharge_datetime、出院记录的 discharge_date 均为空，但 discharge_time 有值。三个选取病历入口均遗漏这个字段，导致已出院病例识别为 running，冻结任务日而非出院日。

DischargeRecord 模型将 discharge_time 定义为“出院时间”（DateTime）；现有 hospitalization_status_service 已读取该字段。本次仅在 RecordRepository 主查询、显式 ID、显式病例坐标三个入口增加末位空值回退。保留原有非空业务日期优先级，禁止以 update_time 代替出院时间。既有冻结主链负责传递截止，不增加第二资料链。

生产改动只有 record_repository.py 的三行。没有新增独立职责或拆分模块；未改旧 source reader、规则算法、API 或前端。

## 验收

- 新增 12 项真实 SQLite collect_records 测试，覆盖三个入口、精确出院时间冻结、已有日期优先、全部业务时间为空及出院日筛选。修复前 time-only 场景三项失败，修复后通过。
- 新旧病历入口、出院业务时间、冻结入口、Provider 共 168 项通过，pytest 执行 2.32 秒。
- 原包离线 Provider → 007 → binding → finalizer 对照：任务日 9 月 9 日截止为 non_compliant / threshold_exceeded，至少需要补 72 个时间点而未知时间记录只有 1 份；出院日 2 月 9 日 08:31 截止为 data_gap / authoritative_time_missing，3 份查房中 1 份缺时间。两边均保留 3 条证据定位，0 次 LLM 调用。
- 原包缺当前 unstable_order 来源；离线回放按当前查询条件从包内完整未截断的 22 条医嘱投影，确认无病危/病重信号。不是把缺源伪造为空。
- ESLint 0 错误、11 条既有 RuntimeBuildStatus 格式警告；使用不带 --fix 的命令以保护工作区现有改动。
- npm check:encoding 返回成功但扫描 0 文件，另对本轮文件严格核对 UTF-8、无 BOM、LF；git diff --check 核对。

## 剩余边界

已有非空日期之间的优先级和冲突处理未扩大修改；本次仅修复所有既有业务日期为空的遗漏。真实病例 007 仍需补齐那份查房记录时间才能确定；不能据此宣称所有待处理项已清除。

本次为源码修复和离线验证，没有改写旧任务结果或重打、部署客户包。新任务才会按新入口重新识别并冻结。
