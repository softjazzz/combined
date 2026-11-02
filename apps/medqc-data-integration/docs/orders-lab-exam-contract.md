# 医嘱、检验与检查报告独立验收合同

本轮只发布到 `medqc_bundle_time_clone_20261029180906`。六接口尚未加入正式生产
worker注册表，不改七接口既有合同或冻结同步器。合同是静态显式映射，运行时不按
相似列名自动猜测。

## 证据与范围

完整有序源字段来自第一轮字段研究包，SHA256
`019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71`。
本轮raw及实际056目标catalog来自已校验报告包，SHA256
`ede696a9df5d747532d4afaa29f2c962767fe4d4e2ecb0dc2b963b6c90072428`。
ZIP外部哈希和8个内部校验均通过；无患者值。此前“17–37%”应是匹配17–37列。

| 源接口 | 源列 | 本次映射目标列 | 实际目标总列 | 新raw行数 |
| --- | ---: | ---: | ---: | ---: |
| inpat_drug_order | 61 | 38 | 40 | 8622 |
| inpat_nondrug_order | 45 | 31 | 33 | 24616 |
| labtest_master | 48 | 25 | 25 | 3269 |
| labtest_item | 28 | 14 | 14 | 5601 |
| labtest_item_report | 37 | 27 | 37 | 42391 |
| exam_item_report | 43 | 22 | 42 | 899 |

映射列数不是临床事实覆盖率；未提供的目标列不伪造，所有未投影源字段继续留raw。
实际目标列类型已逐项与回传catalog核对。长度仍须在客户机从实际catalog读取并校验，
超长不可截断；本轮不改表结构。

## 身份与粒度

- 医嘱保留病例三键+order_id，药品/非药品来源不跨表合并。
- 检验申请保留三键+test_id，项目保留三键+test_id+test_item_id。
- 检验结果每行独立，document_id明确取print_order_id，item_id取test_item_id。
  print_order_id是结果行标识，不能当HIS医嘱号。raw的test_id+print_order_id唯一仍
  不保证较粗目标键唯一，写前必须整批检查三键+document_id，冲突即停。
- 检查报告document_id使用版本化技术标识：`cache-exam-v1:`加SHA256。
  哈希输入为紧凑JSON数组 `[接口名,机构,患者,就诊,exam_id,exam_item_id]`，全部
  保留字符串和原有前导零，不含正文、时间、窗口或行号。源exam_id、exam_item_id
  分别保存为exam_id、item_id，原完整键还在raw。该技术标识不是HIS/PACS申请号。
- 检查报告不匹配HIS医嘱、不解析名称/部位、不推断模态，本轮不派生exam_master
  或exam_item，也不借report_time填exam_time。

## 值与时间

同名字段按JSON清单投影，`inpatno→inpat_no`、`mrno→mr_no`按接口显式映射。
labtest_master同时提供inpatno与inpat_no时，目标用原inpat_no，另一列留raw，不合并。
报告的report_datetime只映射report_time，不写submit_datetime。两种医嘱的开立、
计划、审核、执行、撤销与审计时间各自保留，不从计划时间推断实际执行。
医院本地时间按UTC+08转换，异常日期阻断接口投影、raw不改。

结果、单位、异常标志及referencevalue_min/max保留原字符串，包括不等号、阴性、
空值和参考范围文本。referencevalue_max可能包含整段文本，不能强转数值或拆成
伪造上下限；本轮不拼装reference_range。不根据源空正文生成临床正文，不从报告状态
补造文书提交/签署状态。检查所见description与impression完整保存。

## schema元数据补录

JSONB键顺序不能证明ODBC列顺序。合同给出历史原始有序字段，标准库
`ordered_schema_hash()`只实现已冻结的ordered-column-names-v1算法。
客户机须先检查原抽取代码、raw的实际schema_hash/版本及本地dry元数据；只有
实际hash、算法和字段合同一致，才补缺失的source_schema记录。不能改raw的hash、
payload或版本历史来凑一致，也不能用排序后的JSONB键冒充原始列顺序。
无法证明的元数据先报告，暂停CDM写入；不重抽源数据。

## 验收边界

纯转换器和13项标准库测试不建立连接。现有worker的38项测试仍通过。
客户机负责元数据补录、六接口两轮CDM投影及正式bundle/只读规则源验收。
正式bundle可能把多条检验结果组为一张报告，不能用报告张数直接比较结果行数；
应另核对每张报告的项目/结果行计数。raw窗口不证明全住院覆盖。
