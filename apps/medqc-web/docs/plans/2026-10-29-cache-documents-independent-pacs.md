# Caché 主要文书映射及 PACS 独立证据

## 已确认的边界

客户要求先完成 Caché → raw → 现有 CDM → 正式 bundle 的独立库验收。
检查报告和 HIS 医嘱可能来自不同系统，本次不要求二者编号关联，也不开发名称配对。
本工作树为 `codex/data-integration-service`，基线 `cedb9c10a`。

## 字段合同

`apps/medqc-data-integration/contracts/major-document-contracts.json` 冻结七个接口的
完整有序源列、显式 alias、目标类型、原始键及 CDM 主键。证据为三天字段研究包，
SHA256 `019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71`。
独立转换器及客户机接续说明位于该模块的 `tools/` 和 `docs/`。

客户应用 revision 为 `20261022_000051`。发布前读取实际 catalog，核心列和主键
必须满足合同；可选列缺失需逐项报告并保留 raw，不要求客户升到开发机 revision。
入院及出院记录的现有三段主键不能容纳同病例多文书；遇到该情况必须阻断对应接口
投影，不能覆盖已有文书。日期异常同样保留 raw 并报告，不用其他时间补齐。

`daily_course_record.record_datetime` 在当前 ORM 没有目标列，暂留 raw 并明确列为
事件时间语义缺口。全文验收成功不表示记录时间或签署时间已经齐全。
提交时间、修改时间和 Save 状态均不能代替签署证据。

## 质控消费端调整

- 影像主记录及报告存在时，缺少 HIS 医嘱来源或 PACS 医嘱号无法连接 HIS，不再阻断
  影像报告相关规则；既有微生物培养逻辑不变。
- 不通过名称或时间猜测配对，不从无关医嘱借用开立时间；仍按既有检查及报告时间
  合同核对病程。
- 保留影像记录自身身份冲突、缺报告及缺权威时间的资料缺口。重复检查按不同
  `exam_id` 保留独立事件。此改动不能作为“已执行某条 HIS 医嘱”的证据。

## 验证与发布

开发机仅运行 fake 单元测试，不连接客户 Caché、PostgreSQL 或模型服务。
客户验收限定 `medqc_bundle_acceptance`，现有 `medqc`、`medqc_cache_poc` 及其
checkpoint 不变。先做 raw → CDM 全文哈希与键粒度比较，再调用客户应用原有
bundle 装配入口；逐例区分领域投影上限与真正的数据遗漏。
本次七接口三天窗口不能证明住院全时段或当前在院病例覆盖完整。
