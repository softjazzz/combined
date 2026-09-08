# 首次病程缺失结果保存与诊断导包复测

## 问题与最小修复

本地 CUSTOMER_TEST 单病例任务 `83a4ad3e-f87e-40cd-b4b8-1b2b4f96f0bd`
在规则执行后保存失败：002 为 non_compliant / required_document_missing，
但缺少 customer_display_facts，CanonicalResultStore 拒绝客户解释合同。
失败任务 summary 保留了规则输出，已只读复现同一校验异常，未修改历史结果。

根因是 native_basic_timeliness 的首次病程空来源分支：成熟度判定完成后直接退出，
没有像其他时限分支一样交付现有受控事实。生产修复仅增加12行，复用
timeliness_fact / add_customer_fact；仅 missing_decision 为 None 时输出缺失事实。
此文件已超过行数预警，但本次只补现有分支漏字段，不增加独立职责或拆分模块。
不改状态、原因码、证据引用、医学口径、Finalizer、Store、API 或前端。

## 回归与复核

- 新增回归先失败于 canonical_result_store 的同一解释校验，1失败/2通过。
- 补丁后基础时限测试文件119项通过；主代理另跑Canonical交付及事实投影99项通过。
- 新增回归贯穿 typed session、native、binding、聚合、公共证据投影和保存解释校验。
  未成熟窗口和缺权威入院时间保持原 data_gap，无错误缺陷事实。
- 独立静态审查通过，主代理亲审生产及测试差分。
- 编码脚本成功但扫描0项；对修改Python文件显式UTF-8无BOM/LF检查通过。
- ESLint以 --no-fix 执行，0错误/668警告；git diff --check通过。
  本次只改Python已有分支，未运行全量TypeScript与前端全量单测。
- 前一轮导包聚焦前端测试14项通过；本次未改前端，未重复执行。

## 同病例公开入口复测

重启实际8001 API进程后，从终末质控页面运行同一测试病例。
新任务 `48fce77d-e23c-4b99-9186-b68c2fc68a25` completed，成功1份、失败0份，
72项保存并由页面回读。72项的status/reason_code与失败基线完全一致：
2项确定问题、2项合规、53项不适用、9项资料不足、6项未执行、0项技术错误。
002客户证据与基线一致，只新增缺失事实、8小时时限和权威入院锚点。
任务记录Token均为864；wall_clock_time从3.78秒到2.76秒，单次观测不宣称性能提升，
也不把任务记录Token当作独立核算的实际模型消耗。

## 诊断包浏览器验证及限制

完整结果抽屉可打开诊断导包，预览含72个规则段落、24074字符。
预览包含002的missing/threshold_hours=8事实；本例原姓名、患者ID、住院号均未命中。
未勾选确认时下载禁用，勾选后可发起下载。

Codex内置浏览器CDP实际记录 Page.downloadWillBegin，文件名qc-diagnostic.md，
预期46568字节；随后Page.downloadProgress为canceled、receivedBytes=0。
默认下载目录未发现本次新文件。因此已证明按钮发起下载，但未证明文件成功落盘，
不能把组件测试、预览成功或旧下载文件当成本次下载成功。
已请用户在日常浏览器验证同一入口；完整引擎ZIP回放不属于本轮修复范围。
