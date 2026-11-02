# 日常病程源记录时间补齐

用户已授权补齐正式字段、迁移及映射；客户机本轮仅核对首页正文和签署字段，不重抽。

## 字段与迁移

`DailyCourseRecord.record_datetime` 使用可空的 `timestamp without time zone`，按医院
本地 UTC+08 解释，与既有首次病程和入院记录的 `record_datetime` 类型一致。
新增 `20261029_000056`，父版本 `20261026_000055`。只增加列，没有服务端默认值，
不把提交、签署、修改时间写进该列，不修改已有正文、键或时间。已存在相同列时核验
类型、可空和无默认值后跳过；不同合同阻断，不执行改类型或覆盖。降级不自动删列。
正式初始化入口同步固定到新 head，旧部署尚未升级时仍保持原 revision。

## 映射与读取

字段合同版本为 2；有序源列及 raw 键、schema hash 算法不变。源字段
`web.daily_course_record.record_datetime` 只映射到同名目标列。空值保持 NULL，
异常日期保持原值在 raw 并阻断该接口发布，不猜时间。旧 051 目标没有列时明确报告
raw-only；新合同本身不会对数据库执行迁移。

现有 bundle 目录、timeline 和规则源白名单已支持此列，无需新增回退逻辑。
仅补字段不会更新既有 CDM 或缓存 bundle；后续获准后可使用已有 raw 定向重投影，
无需再次访问 Caché。当前客户机保持 051，不复制单条 056 跨过 052–055、stamp 或
手工 ALTER TABLE。

## 本轮客户机核查

只使用 `medqc_bundle_acceptance`，检查首页 `record_content` 的实际 catalog、空值和
raw→CDM一致计数；六类文书的签署列区分“目标列不存在”“源字段未提供”“源值为空”
和“非空源值已保存”，不把后者直接标记为临床有效签署。源状态/提交人不能补签名。
既有 raw、42个抽取批次、checkpoint 和 bundle 都不改动，不运行质控。

开发机以 PostgreSQL 方言 DDL、迁移图、ORM 合同、纯转换及合成 bundle 测试验收；
不连接真实 PostgreSQL、Caché 或模型，不宣称已做真实 PG 升级。

定向结果：后端83项通过、3项需要专属PG的集成测试跳过；接入38项及独立转换5项
通过，Ruff及接入strict mypy通过。新增迁移另用内存SQLite验证旧值保留及重复运行；
它不能替代真实PG的升级演练。工作树未安装前端依赖，ESLint/vue-tsc/Vitest无法启动。
与v1冻结包逐接口比对，七接口有序源列及raw键均未变化，不需要重抽源数据。
