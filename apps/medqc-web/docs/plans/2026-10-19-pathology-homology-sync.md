# 病理报告定向直读 homology

## 已确认的问题

客户在 Navicat 分别执行两库只读查询，C23/C25 共 5 份报告的申请序号、病理号、北京时间报告时间、审核状态、标本名称长度、肉眼所见长度全部对应，申请序号均唯一，clinical_data 删除标记均为 0。

homology 的 `pathology_exam_report.diagnosis` 五份均有值，长度分别为 14、268、6、48、37 字符；clinical_data 对应表没有该列。此次确认的是同一批报告的字段传递缺口，不能归因为医院未提供病理诊断。客户旧导出包的表结构也确认本地 `diagnosis` 类型为 text；代码模型、规则快照和文书装配已有该字段。

用户已明确授权：核对一致后定向修复病理报告同步来源，其他文书先不动。在 `C:/medqc-agent-merge` 的 `codex/business-agent-integration` 实现。

## 改动

- 复用客户样本与常规同步共用的 `CaseSetSyncService`，只为 `pathology_exam_report` 增加受控 homology 路由。病理申请主表及其他文书沿用原来源。
- 新增独立开关 `HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED`，默认关闭；既有 `HOMOLOGY_SYNC_ENABLED` 仍只控制原五张医嘱/检验表，两者互不启用。共享数据库、schema 与显式机构绑定配置。
- 用完整病例坐标和 `pathology_exam_id` 标识报告，沿用既有病例内快照替换和数据库事务；保留诊断、病理号、状态、肉眼所见、报告时间原值，不生成另一套报告标识，不改变规则判定。
- 预检要求源表有稳定标识及 `diagnosis` 列、本地有 `diagnosis` 列。适配时发现缺列、缺申请标识或重复标识，在病理快照替换前报错；诊断字段存在但值为空的待报告记录仍可同步，不补造诊断。
- 普通来源异常不触发混源补取；沿用既有空结果、同步失败和 Bundle 刷新合同。没有新增数据库迁移、模型调用或重试层。

## 本地验证

全部使用合成数据和替代数据库会话，不连接医院、不写业务库、不调用真实模型。先补回归，原实现下新病理范围 7 项失败、1 项通过；修复后通过。

1. 同步、预检、现有医嘱检验、真实 UPSERT 参数投影、病理展示和 Bundle 回归 **217 项通过**。
2. 客户样本、常规运行 Bundle、病理规则回归 **343 项通过**；与上一组不同测试文件，合计 **560 项**。
3. 合成 1+4 份报告复用已核实的诊断长度，验证全部 5 份按真实 CDM 主键写入，268 字符诊断不截断，规则输入与文书展示保留完整诊断；报告状态与医院本地报告时间保持原值。原始输入机构不被就地修改。
4. 仅启病理开关时，会诊、手术及原五表仍走原来源；只启旧开关不会启用病理。覆盖源/目标诊断列缺失、申请号缺失/重复、待报告空诊断、连接失败和空结果。
5. Ruff、类型检查、无自动修复的 Lint 通过；Lint 0 error、1361 warning。暂存区编码检查另在提交前执行。
6. 前端全量以医院时区、4 worker 运行，因 Windows 虚拟内存不足导致 worker OOM 中断，未宣称通过；同时运行的后端补跑曾遇到 WinError 1450，减少并发后 217 项已完整复验。客户脚本测试需从应用目录运行，已修正首次导入目录错误。未改前端文件。

后端核心命令（在 `apps/medqc-web/backend`）：

```powershell
py -3.10 -m pytest tests/unit/test_homology_sync.py tests/unit/test_homology_evidence_migration.py tests/unit/test_case_set_sync_service.py tests/unit/test_sync_consistency.py tests/unit/test_pathology_eye_findings_migration.py tests/unit/test_document_assembly_pathology.py tests/unit/test_domain_bundle_assembly.py -q --tb=short --disable-warnings
ruff check app/services/homology_sync.py app/services/etl_sync.py tests/unit/test_homology_sync.py
```

客户/规则命令（在 `apps/medqc-web`，不能在 backend 内运行首个脚本测试）：

```powershell
$env:PYTHONPATH = 'backend;.'
py -3.10 -m pytest backend/tests/unit/test_benchmark_customer_sample_sync.py backend/tests/unit/test_custom_qc_sample_pool_service.py backend/tests/unit/test_customer_sample_validation_e2e.py backend/tests/unit/test_sample_source_coverage_audit.py backend/tests/unit/test_running_final_bundle_orchestrated.py backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py backend/tests/unit/test_luxian_0609_019_senior_source.py -q --tb=short --disable-warnings
```

## 部署与真实验收边界

代码修复不等于客户机已更新。当前未修改真实 `.env`、未切换运行配置、未重启、未重新同步或打包。部署新代码后，在客户机 `backend/.env` 新增：

```dotenv
HOMOLOGY_PATHOLOGY_REPORT_SYNC_ENABLED=true
HOMOLOGY_DATABASE=homology
HOMOLOGY_SCHEMA=graph3_homology
HOMOLOGY_SOURCE_INSTITUTE_ID=机构号
HOMOLOGY_TARGET_INSTITUTE_ID=泸县人民医院
```

保留原 `HOMOLOGY_SYNC_ENABLED` 值及主源库配置，不为此次病理修复连带启停医嘱/检验来源。该修复本身不需要新增迁移；正常预检仍应通过。

重启后端后重新同步 1016 样本 C23/C25。真实验收须确认预检来源为 `homology.graph3_homology.pathology_exam_report`，本地原 5 份报告标识和时间对应、诊断 5/5 有值且字符数一致，规则材料和文书对照可读到诊断。之后才重跑依赖病理报告的质控。历史已保存结果不会自动改写；本轮尚未完成这项客户机部署验收。
