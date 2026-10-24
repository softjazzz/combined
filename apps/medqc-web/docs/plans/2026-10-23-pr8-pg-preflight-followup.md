# PR8 复审后 PG 前置检查修复

## 固定点与归因

- 复审 head：`0c14ed26f1081161e74c486c30e166b57110b224`；固定 base：`8c56466e906cad9c2926464ad9c8ff5d3cfbf635`，不移动。
- 已确认两项 P1 授权修复、一项 P2 导出修复的代码结论不变。复审没有执行真实 PG；不能把 SQLite、mock 或浏览器合成 API 证据写成业务库验收。
- 新确认 P2：PG 测试仍用 revision 57 的字符串下限，但新增账号夹具读取/写入迁移 76 的 `SysUser.institute_id`；旧基线能越过旧门禁后因缺列失败。这是测试前置遗漏，不是运行时越权。

## 修复

- 原非生产库显式 opt-in、库名、PG 类型、连接超时均保留；没有实际执行此 opt-in。
- `scripts/manual_review_pg_preflight.py` 在任何夹具写入前开启 **READ ONLY** 事务，核对实际库名、缺陷表的 qc schema，然后调用应用同一 `resolve_user_owner_schema`。
- 对实际解析出的 sys/public 账号表核对完整模型列、id 主键、username 唯一约束、机构 VARCHAR(128) 可空无默认值与机构/科室索引。不能借另一张完整同名表掩盖实际 owner 缺列。
- 对 qc 缺陷/历史核对模型列、id 主键、origin/manual review/scene CHECK；额外无法填充的非空列拒绝。保留 CAS、自审、历史同事务、合成账号和缺陷精确清理代码。
- 不再用 revision 字符串大小推断祖先关系或分叉兼容；本门禁直接验证本测试所需结构，不声称迁移全链已经验证，也不提供 stamp 或迁移操作。

## 验证边界

- 离线 runner 禁 dotenv、网络、非 SQLite 连接；覆盖缺机构列（旧 57 基线）、不明 owner、双表按配置选择及实际 owner 缺列、列/索引/唯一/CHECK 漂移、scene 缺失、完整结构放行、只读语句顺序、库名错误提前拒绝。
- 真实 PG 五项保持跳过。没有连接实际 PG、写业务库、运行真实质控/模型、部署、打包或合并。
- 定向结果：`py -3.10 scripts/run_pr8_offline_tests.py tests/unit/test_manual_review_pg_preflight.py tests/unit/test_manual_defect_review_pg_integration.py tests/unit/test_manual_defect_review_service.py` 为 **51 passed / 5 skipped**；三份 Python 文件 Ruff 通过。首次执行暴露 CHECK 的 TextClause 不能求布尔值，改为显式 None 判断后通过。
- 业务集成线适配另开 `codex/pr8-business-report-adapt-20261023`，工作树 `C:/medqc-pr8-adapt`，从本机已提交 `754fa2f7af23e9d60209f3cbbcf96e3d59d9813f` 起步（含远端 `8c005ee08` 之后的 7 个产品提交）。原工作树未提交改动不搬运、不覆盖；适配提交不掺入 PR8。
