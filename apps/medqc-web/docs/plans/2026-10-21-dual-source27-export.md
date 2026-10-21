# 27例双源完整导出

用户要求重新按双库同步方式导出27例。只在 `C:\medqc-safe-source-sync` 的 `codex/safe-source-sync-20261021` 实现独立工具，不部署、不写数据库、不调用模型，不改变主集成工作树。

## 输出与边界

1. 首先通过已验证的本地导出器备份27例在 `medqc` 的 `cdm/public` 全部具备就诊三坐标的业务表，包含各表完整列，保留原有数据。该备份可独立保留，也嵌入新数据包。
2. 对双源策略覆盖的23张表，分别读取 `clinical_data.public`、`homology.graph3_homology` 和本地 `cdm` 的完整原始列，不限于目前映射字段。来源缺表、读取失败和零行明确区分；失败时不产生最终成功包。
3. 按现有只读双源策略生成逐条候选及来源、冲突、未映射字段、跨药品/非药品医嘱同号的复核清单。原始两侧内容均在原始文件中保留，不拼接冲突正文，不覆盖本地非空数据。
4. C18重点校验3份输血记录、1份出院记录的编号与实际文书组装，要求内容非空且核对字段不丢失。`Save` 原样保留，不据此认定草稿或正式提交，记录有效性保留待确认。

这是 `medqc_dual_source_case_archive_v1` 新格式，包含全量本地基线与双源原始数据，不是仅新增医嘱的增量包，也不是两家源库所有表的完整备份。旧导入器不得直接使用它；清单与候选 `ready_for_import=false`，根清单故意不提供旧格式的 `tables`，防止旧导入器静默漏掉候选。后续导入应先核对冲突、映射及有效性，并使用匹配新格式的处理工具。

## 实现

- `backend/scripts/export_dual_source27.py`：备份、分表全列读取、原始JSONL及候选归档、作用域与校验和验证。成功校验后才把 `.zip.partial` 改名为最终ZIP；失败仍保留先前完成的本地备份。
- `backend/scripts/preview_dual_source27.py`：增加显式 `full_columns` 参数，默认预览仍只读原有投影字段。
- `tools/export-medqc-dual-source27.ps1`：独立入口，不包含 Apply、DDL、DML或模型入口。
- 工具分发包包含私有的27例坐标及既有本地全量导出器，均不提交Git；不包含 `.env`、凭据或病历正文。

每个源使用独立只读可重复读事务；本地初始备份与后续3个源快照不是跨库原子快照，清单记录各源快照时间。单表最多100000行，达到上限时报未完成，不截断后冒充完整。完整文本、NULL、空字符串、多行正文保留；日期、数值、二进制等按列类型及显式编码归档。

## 验证

只运行导出及预览相关的18项离线测试，全部通过；Ruff通过。覆盖三源只读连接、27例完整坐标边界、69份源文件与23份候选文件、额外未映射字段保留、C18实际组装、错误中断、旧导入隔离及归档篡改拒绝。未重新运行全项目检查，未连接医院源库或调用模型。

另在本机PG完成真实只读备份集成验证：27例、157张具备就诊坐标的表、34231行，归档作用域和多行CSV校验通过；此行数是本机快照，不代表客户机源端的新导出行数。分发包解压后完成私有坐标一致性、备份模块、双源策略、实际文书组装器加载及PowerShell语法校验，未连接源库。

客户机双源真实导出须执行以下命令；之前的v2预览已完成27例23表读取，此工具导出的是完整行而非预览计数。只有收到本次成功包后，才能确认本次完整原始数据归档完成。

## 客户机命令

把工具ZIP复制到 `D:\medqc` 后执行：

```powershell
Expand-Archive `
    -LiteralPath 'D:\medqc\medqc-dual-source27-export-20261021.zip' `
    -DestinationPath 'D:\medqc\dual-source27-export' `
    -Force

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\dual-source27-export\export-medqc-dual-source27.ps1' `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.4\backend' `
    -OutputDir 'D:\medqc\exports-dual-source27'
```

输出目录下 `backups` 保存原本地备份，顶层 `medqc-samples27-dual-source-*-private.zip` 为成功导出包，包含原始病历资料，按私有病历文件保管。不传 `.partial` 文件作为完整结果。
