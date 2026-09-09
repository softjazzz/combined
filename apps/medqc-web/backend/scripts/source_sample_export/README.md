# 客户机源库结构探查与后续10次住院样本导出

本次交付**阶段1可执行工具**。阶段2必须等客户机探查结果带回并完成关联审查后再生成，当前没有可执行的数据导出或导入命令，不能拿旧脚本代替。

## 阶段1：客户机操作（只读，不读取病历正文）

### 文件与前置条件

将交付 ZIP 解压到 `D:\medqc\source_sample_export`。这个目录中应直接有：

- `probe_source_schema.ps1`：PowerShell 启动入口，兼容 Windows PowerShell 5.1。
- `probe_source_schema.py`：独立探针，不加载项目配置，不调用质控或同步代码。
- `cdm_dictionary.json`：从用户指定 Excel 提取的150个表条目及字段、逻辑键和父表说明。
- `README.md`：本文。

客户机需能够连接源库，并已有 Python 3.10+ 和 psycopg2。项目后端使用 PostgreSQL 时通常已安装，不要求装 psql、pg_dump、Navicat 或 Excel。

先在普通 PowerShell 控制台执行（不要在 ISE、带输出重定向的密码输入或自动化任务中执行）：

```powershell
py -3.10 -c "import sys, psycopg2; print(sys.version); print(psycopg2.__version__)"
```

如找不到 `py` 或导入失败，使用**后端实际使用的 Python**，例如：

```powershell
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe' -c "import sys, psycopg2; print(sys.version); print(psycopg2.__version__)"
```

若该解释器仍无 psycopg2，由管理员给该解释器安装项目依赖；离线客户机可使用项目已有 wheel 包。工具不会联网安装任何东西。

### 开始探查

把以下四个配置改为客户机能够访问的**源库**连接信息。不要误填项目本地库。密码将在控制台交互输入，输入时不回显，不写入参数、脚本、环境变量、日志或输出文件。

```powershell
$probeConfig = @{
    Server = '填写源库地址'
    Port = 5432
    Database = '填写源库数据库名'
    Username = '填写源库账号'
    OutputDir = 'D:\medqc\source_schema_probe'
}
& 'D:\medqc\source_sample_export\probe_source_schema.ps1' @probeConfig
$probeExit = $LASTEXITCODE
Write-Host "Probe exit code: $probeExit"
```

默认探查全部非系统 schema，避免只看 public 而漏掉其他 schema 中的CDM。若管理员确认只需 public，可在运行前执行：

```powershell
$probeConfig.Schemas = @('public')
```

指定后端解释器可在运行前执行：

```powershell
$probeConfig.PythonExe = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe'
```

支持 `SslMode`（默认 `prefer`，遵循现有连接环境）、`StatementTimeoutSeconds`（每个目录查询默认60秒）。证书校验环境可设置 `verify-full` 并沿用 PostgreSQL 客户端证书配置；不要为了运行探针降低客户既有安全要求。

若执行策略阻止 PS1，无需修改全局策略，可直接运行 Python 入口：

```powershell
py -3.10 'D:\medqc\source_sample_export\probe_source_schema.py' `
  --host '填写源库地址' --port 5432 `
  --database '填写源库数据库名' --username '填写源库账号' `
  --output 'D:\medqc\source_schema_probe'
```

### 输出与成功标志

每次创建独立目录及对应 ZIP，例如：

```text
D:\medqc\source_schema_probe\source_schema_20260909T080000Z_a1b2c3d4\
D:\medqc\source_schema_probe\source_schema_20260909T080000Z_a1b2c3d4.zip
```

名称是UTC时间和随机运行标识。终端会打印实际 ZIP 完整路径。

| 标志/退出码            | 含义                                 | 操作                                         |
| ---------------------- | ------------------------------------ | -------------------------------------------- |
| `PROBE_COMPLETE` / 0   | 所有系统目录查询成功                 | 带回该次 ZIP                                 |
| `PROBE_INCOMPLETE` / 2 | 连接失败或至少一个目录查询失败       | 仍带回该次 ZIP；查看 manifest 和失败 section |
| `PROBE_FAILED` / 1     | 前置依赖、输出路径、字典、输入等错误 | 先核对终端报错及文件；不能当成功结果使用     |
| `PROBE_ABORTED` / 130  | 人工中断                             | 该次可能没有完整 ZIP，重新执行               |

目录查询每项独立保存状态；出错会回滚到保存点再继续，连接断开则剩余项标记 `not_run`。不会把失败写成空数组，产生“表不存在”的假象。没有业务表记录数：清单的 `metadata_row_count` 是目录元数据条数。

输出内容：

| 文件                                            | 内容                                                               |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| `manifest.json`                                 | 本次范围、完整性、各项状态、文件字节数及SHA-256                    |
| `connection.json`                               | 数据库、账号、PG版本、编码、时区、只读隔离级别、快照和角色RLS属性  |
| `schemas.json`、`relations.json`                | 全部实际表/分区表/视图/物化视图/外部表和权限                       |
| `columns.json`                                  | 全部实际字段、顺序、类型、精度标记、NULL约束、默认值、注释和列权限 |
| `constraints.json`、`indexes.json`              | 物理主外键、列对应关系、检查约束、唯一索引等                       |
| `views.json`、`view_dependencies.json`          | 视图定义和对象依赖，不执行视图，不是可直接使用的业务JOIN           |
| `inheritance.json`、`types.json`                | 分区/继承关系，自定义类型、枚举、域等                              |
| `row_security_policies.json`、`extensions.json` | 行级策略、扩展版本                                                 |
| `dictionary.json`、`dictionary-comparison.json` | 字典原始定义、同名对象、字段缺失/新增及权限判别                    |
| `queries.json`                                  | 本次使用的固定目录SQL，便于审计                                    |

字典目录有150个条目；提取后有6,350个字段条目（保留字典原文，不视为已验证的数据库列）。`medical_insurance_settlement_surgery` 未匹配同名字段页，标记 `sheet_status=missing`，不得据此认为源库缺表。

另外，住院处方明细的 `prescription_id` 父表原文是 `intpat_prescription`，与目录的 `inpat_prescription` 不同。该疑似拼写错误原样保留，待实际结构确认后明确修订关联方案，不自动猜测替换。

### 如何理解权限和缺失

- `not_found_in_selected_catalog`：目录查询成功，但本次选定schema中未发现同名表/视图。不是“源库全局不存在”的结论；也可能有schema选择、命名或大小写差异。
- `catalog_unavailable`：目录本身查询失败，不能判断对象有无。
- `no_schema_usage` / `insufficient_select_privilege`：看到了对象，但当前账号缺权限。不能当空表或缺表。
- `select_privilege_present_not_executed`：权限元数据允许读取，但阶段1没有真正读取业务对象；底层视图依赖、FDW远端权限等仍可能失败。
- `row_security_active=true`：业务读取可能被行级策略过滤。阶段2必须解决完整性范围，不能把账号看不见的数据当不存在。
- `complete` 只代表目录探查完整，不代表所有对象可完整导出。目录缺少物理外键也不代表字典逻辑关系不存在。

本阶段只执行 PostgreSQL 系统目录 SELECT 和会话/只读事务控制，无建表、临时表、业务数据读写、EXPLAIN ANALYZE、业务COUNT或质控请求。单连接 `REPEATABLE READ READ ONLY`，结束关闭并回滚；探查数据库连接默认只读，且 `search_path` 固定 `pg_catalog`。

视图定义、默认值、注释属于结构元数据，可能包含客户内部对象名称或配置字面量；不读取 `pg_stat_statements`、业务正文或外部表连接选项。请仍按客户授权范围带回。

### 带回开发机后核验

先解压 ZIP，保持内容原样，不用 Excel 重新另存 JSON。在开发机或客户机执行（本步骤无需连接数据库、无需 psycopg2）：

```powershell
python 'D:\medqc\source_sample_export\probe_source_schema.py' --verify `
  'D:\medqc\source_schema_probe\source_schema_实际运行标识'
```

出现 `VERIFY_OK` 表示各文件未损坏或缺失；另看 manifest 确认查询完整性。清单哈希用于完整性检查，不是防篡改签名。

连接超时先确认地址/端口/VPN/网络；认证失败确认源库账号；`42501` 是权限错误，`57014` 常为超时/取消。工具不会自动提权、修改授权或重试密码。连接阶段失败无SQLSTATE时仅记录异常类型，不保存连接串及可能含密码的异常全文。

## 阶段2：收到结构包后确定，再生成正式执行脚本

### 输入与关联范围

使用一个UTF-8 JSON文件，恰好10组不同的 `institute_id + patient_id + visit_id`，值均为字符串。保留前导零，不自动trim；病案号和住院号不能代替visit_id。由客户确认这10组同次住院身份。

正式方案会为字典150项及实际发现的相关新增表建立覆盖清单，逐项标记：按三元身份直接读取、通过父表间接读取、患者/机构资料、与住院无关、字段/权限/关联待确认。不会只按现有固定表名单或红色必备列导出。

关键原则：

1. 有三元身份的表，使用三列等值匹配；不做 `visit_id IN (...)` 单列筛选。
2. 明细表使用经核实的父子复合键，例如机构+患者+文书号、机构+医嘱号、检查申请号/检查号；保留不同字段名的显式映射。用 `EXISTS` 半连接，避免多父记录造成子记录重复。
3. 缺少机构/患者字段时，必须证实可用关联键的唯一性和命名空间。仅凭同名 `document_id`、`order_id` 或 `exam_id` 不推断JOIN；有跨机构碰撞或歧义就报 `association_ambiguous`，不能静默挑选。
4. 同一行被多个就诊/多条路径选中只输出一次，另保存归属索引。不能通过内容 `DISTINCT` 抹去源表真实重复行；无主键表需单独明确行标识和多重集核验办法。
5. 患者、机构主索引只导关联键命中的行，不扩展到患者的其他住院记录；与住院无关的门诊域明确标记范围外。

字典中麻醉监测/用药/事件明细的 `document_id` 父表说明、处方明细、检查检验报告和文书诊断明细等，会列为重点核对关系。实际名称、键和类型以带回结果为准。

### 原始值与一致快照

计划用 PostgreSQL 原生 `COPY (SELECT 实际全部列 ...) TO STDOUT` 流式写入文件，**COPY text格式**，不是先转Python字典再写CSV。实际列从系统目录按顺序取得，包含字典外新增列；不strip、不替换空值、不映射、不摘要、不限制正文长度。

- COPY text 的NULL标记为 `\N`，空字符串是空字段，字面文本 `\N` 会转义为 `\\N`，空格保留；换行、回车、制表符、反斜杠按COPY规范转义，使用COPY FROM可恢复。
- 固定UTF-8、DateStyle、IntervalStyle、浮点输出精度和时区，并写入清单。保留timestamp微秒，timestamptz按UTC导出保留精确时刻。PostgreSQL本身不保留timestamptz输入时的原始时区拼写，jsonb也不保留原始JSON空白，工具不能恢复数据库未保存的信息。
- 数据导出使用单个只读REPEATABLE READ事务，所有表、关联键、COUNT、COPY使用同一个快照。结构文件与数据快照关联；需要pg_dump时，使用同版本工具并共享导出快照，保持持有快照的会话存活。
- 客户端pg_dump若用于完整DDL，版本不得低于服务端。阶段1不要求安装；带回版本后再提供确切前置要求。
- FDW外部表、读取远程数据或调用非稳定函数的视图，不能凭本地快照宣称全局一致。发现后必须决定由源系统提供稳定快照或改为已确认基础表方案；不能偷偷降级成逐表“近似一致”。
- 数据行数用同快照同关联条件核对COPY导出计数，不按文本换行计数。长事务会维持旧快照，执行时限和10次就诊规模需结合客户环境控制。

### 交付清单与状态

每表清单包含schema/对象名、对象类型、实际字段及顺序、字段数、关联路径、参数化条件、对应10组身份、精确记录数、数据格式/编码、文件字节数和SHA-256。还需源库版本/快照、所用脚本版本、选定身份文件哈希、RLS/权限、全部覆盖表状态。

状态必须区分 `exported`、`no_data`、`not_found_in_catalog`、`permission_denied`、`association_ambiguous`、`failed`、`not_run`、`out_of_scope`。任何必需表/字段失败都不得输出完整成功标志；断线后不能在新快照中继续拼接旧包。

### 开发机独立还原与一致性核验

收到实际类型与关联方案后再提供可执行 `restore` 和 `verify` 命令。目标只能是新建的独立样本库，例如 `medqc_source_samples_20260909`；明确传入目标连接，密码交互输入，不读取项目 `.env` 的 DATABASE_URL、不覆盖开发库、不重建Bundle。

1. 验证所有文件哈希、字段数及清单状态。
2. 在空样本库建立隔离schema和同字段、同类型的原始数据表，再COPY FROM；视图结果作为普通原始表落地，不直接执行客户视图、函数、触发器、RLS或远程连接DDL。枚举、域、复合类型、扩展依赖根据实际结构审查；无法等价还原即停止，不能降级为全TEXT假称等价。
3. 还原使用独立事务，失败整体回滚。附带源结构原文和已审核的还原结构文件，明确二者用途及差异。
4. 核对实际列名/顺序/类型、每表行数以及行内容。若有稳定唯一键，按相同键序COPY再比较哈希；若无唯一键，用保留重复次数的完整行多重集核验，不依赖物理行顺序。
5. 增加NULL/空串/纯空格、CR/LF/制表符、反斜杠、超长正文和时间微秒的往返测试。源表内容、同步CDM和Bundle的比较另行生成报告，不修改原始样本。

当前阶段1的 `columns.json` 等只用于结构审查，**不能直接作为还原DDL**。Navicat可用来辅助查看结构，但不建议分表点选CSV导出承担本次无损、同快照的数据迁移。
