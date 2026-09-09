# 旧入院 Bundle 与入院时间：验证结论

## 受控测试

测试文件：backend/tests/unit/test_admission_stale_bundle_visibility.py。

用合成同次住院资料替换数据库读取，调用真实 assemble_domain_bundle 和 load_bundle_documents。保存的旧 Bundle 缺少 admission_datetime，当前记录已有 2025-08-12 17:24:13，Bundle 结构版本不变；当前资料没有入院诊断附表，避免诊断补全逻辑附带刷新。

- 保留旧 Bundle：页面文书返回没有入院时间章节，未触发入院域强制刷新。
- 仅替换为重新组装的 Bundle：返回入院时间章节，数值与当前记录一致。
- 反例：当前资料有入院诊断附表时，已有诊断补全入口可能重建并覆盖旧投影，顺带显示入院时间。因此并非所有旧 Bundle 都稳定漏显。

## 质控侧

已有 test_luxian_0609_007_gap_details.py 的9项测试覆盖 session、007执行、绑定归并及finalizer。登记时间为空，入院记录 admission_time 有值时，007采用入院记录时间；去掉当前表时间后才返回 authoritative_time_missing。

生产主链通过 source_evidence_reader 直接按机构、患者、就诊读取物理表，不依赖保存 Bundle。不能把前端漏显直接解释为007的数据不足。

## 边界

本次是替换数据库读取的受控回归验证，不是客户机复现，也没有对业务数据库写入旧Bundle。证明该机制可能造成前端缺字段，尚不能确认客户机具体病例根因。没有修改生产逻辑，也未添加刷新按钮或重新打包。
