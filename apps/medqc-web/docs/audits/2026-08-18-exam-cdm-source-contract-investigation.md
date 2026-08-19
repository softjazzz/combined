# 检查/影像源表与 CDM 合同差异排查记录

## 1. 记录目的

- 记录时间：2026-08-18（北京时间）
- 计划续查时间：2026-08-19 上午
- 范围：`exam_master`、`exam_item`、`exam_item_report`，以及 LX0609-010/011/012 使用的检查资料链
- 当前状态：`FIX_REQUIRED / ROOT_CAUSE_NOT_FULLY_CONFIRMED`

本文只记录已经核实的事实、尚待确认的假设和下一轮最小查询步骤。当前客户机已无法访问，因此不能继续完成源库、客户机本地库和应用读取结果的三方对账。

## 2. 当前结论

客户当前 `public` 检查相关表没有严格按《01cdm,V1.0（视图接口。红色为必备部分）》落地；项目现有 ORM、同步配置和规则读取逻辑也存在另一套字段假设。

目前已经确认两类偏差：

1. **字段结构偏差**：正式 CDM、客户实际表、项目 ORM/ETL 三者的字段名不完全一致。
2. **业务键偏差**：正式 CDM 要求主表与报告表通过单一 `exam_id` 关联，但客户 `exam_master.exam_id` 出现组合编码，且已核对样本在 `exam_item_report` 中没有同一次就诊记录。

尚不能确认的关键点：

- 客户 `exam_master.record_content` 是否已经保存完整检查所见和结论；
- 组合 `exam_id` 是源系统原始值、视图拼接结果，还是同步适配错误；
- `exam_item` 是否存在、是否保存组合编码对应的项目；
- 源库与客户机本地库是否使用同一套视图定义和字段映射。

在上述问题确认前，不能把“报告明细表为 0 行”直接等同于“医院没有检查报告”。

## 3. CDM V1.0 的正式结构

参考文件（只读）：

```text
C:\Users\Coldplay\Downloads\01cdm,V1.0（视图接口。红色为必备部分）(1).xlsx
```

### 3.1 `exam_master`

定位：工作簿目录中的 `exam_master`，对应检查申请/检查主记录。

关键字段：

```text
institute_id
patient_id
visit_id
visit_type
exam_id
order_id
exam_type
exam_reason
request_datetime
exam_datetime
report_datetime
exam_result_status
record_content
```

字典备注要求 `exam_id` 表示每次检查的唯一编号。

### 3.2 `exam_item`

关键字段：

```text
institute_id
patient_id
visit_id
visit_type
exam_id
exam_item_id
item_name
item_code
exam_zone
report_datetime
record_content
```

`exam_item.exam_id` 关联 `exam_master.exam_id`。

### 3.3 `exam_item_report`

关键字段：

```text
institute_id
patient_id
visit_id
visit_type
exam_id
description
impression
recommendation
abnormal_sign
device_information
image_id
remark
report_status
report_datetime
record_content
```

`exam_item_report.exam_id` 关联 `exam_master.exam_id`。正式字典中没有 `exam_no`、`item_no`、`document_id`。

## 4. 客户实际表的已确认事实

### 4.1 `exam_item_report` 实际字段

客户数据库返回的字段包括：

```text
v2_schema
is_deleted
institute_id
patient_id
visit_id
visit_type
exam_id
item_id
description
impression
recommendation
abnormal_sign
device_information
image_id
remark
report_status
report_time
record_content
last_modifier
last_modifier_id
last_modified_time
update_time
sys_index_id
record_time
record_status
sys_source_time
```

主要差异：

- 客户表增加 `item_id`、`sys_index_id` 等运行字段；
- CDM 的 `report_datetime` 在客户表中表现为 `report_time`；
- 客户表没有项目代码当前曾假设的 `exam_no`、`item_no`、`document_id`。

### 4.2 数据新鲜度

截至 2026-08-18 的查询结果：

| 表                      |    总行数 | 有业务时间行数 | 最新业务时间（北京时间） | 近7天 |  近30天 |
| ----------------------- | --------: | -------------: | ------------------------ | ----: | ------: |
| `exam_master`           |   220,176 |        220,176 | 2026-08-11 20:50:31      |     1 |   5,823 |
| `exam_item_report`      |   117,807 |        117,807 | 2026-08-10 15:34:24      |     0 |     104 |
| `labtest_master`        |   650,520 |        650,520 | 2026-08-12 11:28:10      |     4 |  18,137 |
| `labtest_item_report`   | 7,179,838 |      7,058,431 | 2026-08-09 20:53:02      |     0 | 234,126 |
| `pathology_exam_report` |    14,349 |         14,349 | 2026-08-05 14:44:00      |     0 |     279 |

此前“检查数据只到 6 月”的截图已经过时；当前真实问题是近期数据有滞后和主报告关联异常，而不是整表从 6 月停止。

### 4.3 `exam_master` 2026-08-08 至 2026-08-12 每日数量

```text
2026-08-08: 25
2026-08-09: 19
2026-08-10: 43
2026-08-11: 12
2026-08-12: 0
```

8 月 10 日不是异常断崖；更需要关注的是 8 月 12 日为 0，以及最新数据停在 8 月 11 日晚间。

8 月 10 日的 43 条主表记录中，已查询的关键标识和报告时间均非空。

### 4.4 已核对样本

为避免在仓库文档保存患者级标识，本文不记录患者号和就诊号。精确坐标保留在本次受控排查会话中。

已确认：

- 同一次就诊在 `exam_master` 中有 12 行；
- 其中一条 8 月 10 日主记录的 `exam_id` 为组合形式（本文脱敏为 `<base>||<item>^<base>||<item>`）；
- 同一次患者/就诊在 `exam_item_report` 中为 0 行；
- 按完整组合 `exam_id` 查询为 0 行；
- 将组合值猜测拆成 `exam_id + item_id` 后查询仍为 0 行。

正式 CDM 字典不支持把 `<base>||<item>`解释成 `exam_id + item_id`。该猜测已撤回，后续不得继续按此规则实现兼容逻辑。

## 5. 项目代码与正式 CDM 的差异

### 5.1 ORM 模型

文件：`backend/app/database/models/cdm.py`

当前 `ExamItemReport` 模型继承 `DocumentMixin`，并假设存在：

```text
document_id
exam_no
item_no
item_name
exam_result
exam_impression
exam_conclusion
```

这与正式 CDM V1.0 和客户实际表均不完全一致。

### 5.2 同步配置

文件：`backend/app/services/etl_sync.py`

当前同步键配置为：

```text
exam_master: patient_id + visit_id + exam_no
exam_item_report: patient_id + visit_id + exam_no + item_no
```

客户实际表没有 `exam_no/item_no`，正式 CDM V1.0 也不以这两个字段定义检查报告关联。

### 5.3 Bundle 报告组装

文件：`backend/app/services/bundles/assembly.py`

当前逻辑优先按 `exam_no` 分组，以 `exam_id`回退；主表和报告表再按字段值精确匹配。面对组合 `exam_master.exam_id` 和空的报告表时，无法形成规范报告关联。

### 5.4 LX0609 检查执行器

文件：`backend/app/services/luxian_0609/native_exam_lab_execution.py`

当前 LX0609-010 使用 `exam_item_report.exam_id == exam_master.exam_id`检查报告关联。该规则本身符合正式 CDM 的精确业务键原则，但客户表当前数据不满足此前提。

另外，当前执行器在找不到报告行时，可能以主表报告时间作为部分完整性依据。因此必须核查 `exam_master.record_content`，不能只看 `exam_item_report` 是否为空。

## 6. 对质控结果的影响

| 规则       | 可能影响                                                                         |
| ---------- | -------------------------------------------------------------------------------- |
| LX0609-010 | 医嘱、检查主记录和报告无法证明属于同一事件，返回 `data_gap / association_failed` |
| LX0609-011 | 无法可靠确定报告内容和出具时间，不能计算报告后24小时记录窗口                     |
| LX0609-012 | 无法读取检查描述、印象和阳性标记，不能确认阳性结果及后续临床分析                 |

风险包括：

- 假阴性：阳性报告存在，但系统关联不到，漏掉问题；
- 假阳性：错误合并不同检查或病程，误判未记录/未分析；
- 大量数据不足：检查事件存在，但报告事实无法安全证明；
- 证据定位错误：报告编号与实际文书无法绑定。

在资料合同修复前，相关规则应继续失败关闭；不得通过拆 `||`、`^`或按数量/文本相似度猜测关联。

## 7. 已排除或撤回的错误假设

1. 不应使用系统归一化机构名称作为源库 `institute_id` 查询条件；源库真实机构标识需单独确认。
2. 客户 `exam_item_report` 没有 `exam_no`，此前包含该字段的 SQL 会直接报错，并非“查询不到数据”。
3. 正式 CDM 不支持把 `exam_master.exam_id` 的 `||`、`^`组合值自行拆成 `exam_id + item_id`；此前猜测已撤回。
4. 单凭报告表 0 行不能判断医院没有报告；必须先核查主表 `record_content` 和视图定义。

## 8. 2026-08-19 上午续查步骤

### 8.1 先确认连接对象

分别记录：

- 源库主机、数据库名、schema；
- 客户机本地库主机、数据库名、schema；
- 两侧 `current_database()`、`current_schema()`；
- 表对象是基础表、普通视图还是物化视图。

```sql
SELECT current_database(), current_schema(), current_user;

SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('exam_master', 'exam_item', 'exam_item_report')
ORDER BY table_name;
```

### 8.2 读取真实视图定义

如果对象是视图：

```sql
SELECT
    c.relname,
    c.relkind,
    pg_get_viewdef(c.oid, true) AS view_definition
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('exam_master', 'exam_item', 'exam_item_report');
```

目标：定位组合 `exam_id` 是在哪一层产生的。

### 8.3 核查三张表真实字段

```sql
SELECT table_name, ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('exam_master', 'exam_item', 'exam_item_report')
ORDER BY table_name, ordinal_position;
```

### 8.4 核查已确认样本的主表内容

用受控会话中的精确患者/就诊/检查标识替换占位符：

```sql
SET statement_timeout = '15s';

SELECT
    exam_id,
    order_id,
    report_time,
    length(COALESCE(record_content, '')) AS content_length,
    left(COALESCE(record_content, ''), 1000) AS content_preview
FROM public.exam_master
WHERE patient_id = '<PATIENT_ID>'
  AND visit_id = '<VISIT_ID>'
  AND exam_id = '<EXAM_ID>'
LIMIT 1;
```

如果实际列名为 `report_datetime`，用真实字段替换 `report_time`。

### 8.5 核查 `exam_item`

```sql
SELECT *
FROM public.exam_item
WHERE patient_id = '<PATIENT_ID>'
  AND visit_id = '<VISIT_ID>'
LIMIT 100;
```

目标：判断组合编码是否来自检查项目表，以及项目表是否缺失。

### 8.6 源库与本地库对账

针对同一安全样本，对比三张表：

```text
行数
exam_id集合
order_id
report time
record_content长度
description/impression
最新update_time/sys_source_time
```

不得只比总行数；必须比相同业务键的逐表结果。

## 9. 决策矩阵

| 续查结果                                         | 处理方式                                                       |
| ------------------------------------------------ | -------------------------------------------------------------- |
| 源库视图已违反 CDM，客户本地只是原样同步         | 优先要求数据方修复视图；同步层不猜业务键                       |
| 源库符合 CDM，本地同步后出现组合ID或丢报告       | 修复 ETL 字段映射和主键配置                                    |
| 主表已有完整报告正文，报告表为空是客户约定       | 冻结一份客户适配合同，在同步层标准化为规范 CDM，不在规则层兼容 |
| 主表和报告表均无报告内容                         | 判定为源数据缺失，向数据方反馈                                 |
| `exam_item_report.exam_id`可与规范主表ID精确关联 | 恢复精确业务键主链，并补真实病例回归                           |

## 10. 完成标准

只有满足以下条件才能关闭本问题：

1. 明确源库、客户本地库和应用CDM三层的字段映射；
2. 明确组合 `exam_id` 的生成来源和合法性；
3. 同一检查事件能通过受控业务键唯一关联医嘱、主记录和报告；
4. LX0609-010/011/012 对同一真实样本得到可解释状态；
5. 证据能定位到真实报告；
6. 缺报告时稳定返回资料待核实，不能误判合规或确定问题；
7. 不在规则执行器中新增 `||`、`^`拆分猜测或弱关联回退。
