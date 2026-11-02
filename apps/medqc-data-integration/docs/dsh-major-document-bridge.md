# DSH 主要文书映射桥接

## 最小交付包

客户机只需复制以下文件，不需要安装本项目、psycopg v3、pyodbc 或任何新驱动：

- `contracts/major-document-contracts.json`
- `tools/major_document_transform.py`
- `tools/test_major_document_transform.py`（可选但建议随包提供）

JSON 只含字段名、类型、映射、主键和证据哈希，不含样本值或连接信息。转换模块仅使用
Python 3.10 标准库。DSH 继续使用客户机既有的 pyodbc 与 psycopg2 连接代码。

解压后先运行不连接数据库的自检：

```text
cd tools
py -3.10 -m unittest -v test_major_document_transform.py
```

## 051 目标 catalog 预检

先从独立验收库读取七张目标表的 `information_schema.columns.data_type` 和 PostgreSQL
主键顺序，分别形成 `catalog_columns: dict[str, str]` 与 `primary_key: list[str]`，再调用：

```python
from major_document_transform import load_contract, preflight_target_catalog

contract = load_contract("major-document-contracts.json")
result = preflight_target_catalog(
    contract,
    "web.daily_course_record",
    catalog_columns,
    primary_key,
)
```

`required_target_columns` 包含病例主键、文档编号、全文和提交时间。任一核心列缺失、
类型不匹配或主键顺序不一致都必须阻断该接口发布。051 中尚不存在的可选时间或签名列
只会出现在 `unavailable_optional_targets`，其源字段继续保留 raw，并出现在
`raw_only_source_columns`；不得为验收临时修改业务 Alembic 或手工加列。
这里的 required 是目标 catalog 列合同，不表示每行正文和提交时间必须非空：合法空正文
保持空串，空提交时间转换为 NULL，并在验收统计中分别计数；不得伪造值。病例主键和
文档编号仍必须逐行非空。

## 行转换

先用 `ordered_source_columns` 严格核对 raw 的 schema，再只转换预检允许的列：

```python
from major_document_transform import transform_row, validate_source_columns

validate_source_columns(contract, interface_name, actual_source_columns)
target_row = transform_row(
    contract,
    interface_name,
    raw_payload,
    result.writable_target_columns,
    completed_at=local_sync_completed_at,
)
```

- 文书全文不截断、不解析、不猜结构化临床段落；
- `documentid/documenttitle/recordcontent` 等仅按 JSON 中的显式 alias 转换；
- `submit_datetime` 只表示提交时间，不冒充记录或签署时间；Save 状态也不等于签署；
- Date 与 DateTime 先按上海本地语义转换成 Python `date/datetime`，再交给 psycopg2；
  带时区目标保留 `+08:00`，异常年份（例如 1840）阻断发布，原值仍在 raw；
- 文本空串保持空串；日期空串转换为 SQL NULL，不当作格式异常。

合同 v2 已增加 `daily_course_record.record_datetime` 的同名投影；正式应用迁移
`20261029_000056` 新增可空无默认值的记录时间列。客户 051 目标无此列时仍作为
raw-only 明确报告，不能用 `submit_datetime`、`last_modified_datetime` 或 `update_time`
代替。该合同不会自动升级客户库；升级和从既有 raw 重投影需按后续部署步骤执行。
`physician_sign` 及其时间列若 051 缺失，
同样作为可选 raw-only 报告，不影响全文验收，也不能据此宣称签署语义已齐全。

## 多文书与事务

raw 的六类文书键均为病例三键加文档编号，因此每份文书都保留。`admission_record` 与
`discharge_record` 的现有 CDM 主键只有病例三键；发布前必须按该三键检查 raw 重复。
同一病例出现多份文书时整接口批次 fail-closed，保留 raw，不能覆盖或任选一条。
四键病程表按文档编号保存每份文书。

七个接口必须逐接口单事务发布；任何 schema、catalog、日期、键或写入失败都回滚该接口
的整个 CDM 批次。不得更新合同未拥有的目标列。

## 三天 bundle 验收

继续只使用独立 `medqc_bundle_acceptance`，不要写现有 `medqc` 或 `poc`。目标表结构必须
来自客户应用当前 `20261022_000051` 的既有 Alembic 链；不要求升级到开发机 revision。
完成目标 catalog 预检和映射发布后，调用客户应用现有 assembly/bundle 入口生成真实
bundle，以病例目录、领域条目数和全文哈希核对两轮结果。DSH 不自行拼装或模拟 bundle。

本轮不开发检查报告与医嘱的跨系统外键或语义配对；两类数据后续分源发布，只验证各自
病例三键归属。在院接口尚无已验证合同，不得加入本次发布或声称已支持。
