# IML01 followup 独立复核：两项确定阻断已关闭，CT/MRI合同待定

固定提交 `8c9df71af38c934570df6402f9251e046c489a98`，父提交 `11211cc42becaa03d0f5b36056bdc3e17a31842a`，工作树 `F:/MedQC-worktrees/qc-fix-ledger-20261008`。只读核对生产diff，不修改生产和原测试；root授权独占轻量槽执行0.59秒后立即释放。无pytest、PG、.env或模型。

## 结论

此前两项确定阻断在本次轻量范围关闭，可合入对应修复：合法培养生化鉴定明细不会再推翻培养主项；结构化整值US及DR可提供独立反证。原CT/MRI同键用例仍实际compliant，与原冻结data_gap预期不一致；因是否允许联合检查合同未获确认，单列待定，不计为通过，不宣称IML01全部争议关闭。

## 冻结和计数

- 原 `expected.json` SHA256 `dbda7a2d78a57e7114ec72879b4300c7a682ae8fa2da35335e737e2fbf2ac05c` 保持不变，原16项15符合/0确定失败/1合同待定。
- 补充 `followup-defaultsql-expected.json` 在执行前冻结，SHA256 `edbd2c902dbdb0a5c8899ac1dd6e61c4905cbad8096e3c16135932db88a69dee`，含培养主项仅item_name候选正常对照1项，符合；默认SQL三新增列存在/缺列各一共6项，6/6符合。
- 私有脚本 `followup_fixed_blob_probe.py`，固定源码及输入哈希、逐项事件关联/状态/原因、生成SQL及投影字段见 `fixed-8c9df71af-results.json`。

## 行为证据

权威血培养/lab_type微生物培养配无项目名报告明细item_name生化鉴定，实际compliant；权威报告labtest_subject血常规仍data_gap。培养报告的lab_item_name/item_name按明细角色排除反证，但主项仅item_name血培养仍进入候选，避免过度排除正常数据。CT主项/CT模态配同键报告modalityUS，实际data_gap。CT介入、CTA、未知其他类别、普通无名报告、正文既往其他影像仍为compliant。原明确CT/DR、超声执行科室、混合CT/DR及同一行名称/模态矛盾均继续data_gap。

默认source reader新增exam_master.modality、exam_item_report.modality、labtest_item_report.labtest_subject。精确固定源码read_luxian_0609_native_source_rows在字段存在时生成SELECT读取原值；缺列时既不SELECT该列、也不从合成行残留字段猜出它。SQL合成引擎按实际SELECT列投影，全部保留三坐标WHERE及有界LIMIT。静态核对snapshot字段表从同一native字段表引用，三新增列会进入对应默认snapshot批准字段。

## 方法和边界

本次用git show读取固定blob，stdlib AST执行原始ledger→报告完整性纯函数及精确默认native SQL读取函数；数据库引擎、列目录和结果是明确的合成假对象，无真实连接。未加载生产依赖或执行完整native→Reducer→Finalizer/Renderer链路；不继承开发390 passed为本报告独立计数。原provider两项旧计数/版本测试失败未重跑，root已说明父提交同因，本报告不把它们归入已修复行为或独立通过证据。

默认读取字段增加会改变具有这些列的真实输入资料及潜在提示，旧CT真实证据不能自动等同当前通过。旧round6 C09/C10移除DR已有输入变化；C12/C04只在完全相同输入下能使用历史响应离线回放。加入modality或报告labtest_subject后，需再确认是否仍完全相同。当前真实模型稳定性仍待真实验证。

可继承修复测试：apps/medqc-web/backend/tests/unit/test_luxian_0609_handbook_identity_conflict_closure.py。本报告未改该文件。
