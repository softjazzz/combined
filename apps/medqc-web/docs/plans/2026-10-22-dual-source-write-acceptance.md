# 正式双源写入与客户机小范围验收

实现目录：`C:/medqc-safe-source-sync/apps/medqc-web`，分支：`codex/safe-source-sync-20261021`。本次不改集成工作树，不部署，不改数据库结构，不启动质控或调用模型。

## 正式入口

普通病例同步、客户样本同步共用的 `CaseSetSyncService.sync_case_set` 已接入新写入器。`DUAL_SOURCE_SYNC_ENABLED` 默认 `false`，原同步入口保持现状。本次没有修改任何运行配置或启用开关。

将来部署并开启时，需显式配置 `HOMOLOGY_TARGET_INSTITUTE_ID`、`HOMOLOGY_SOURCE_INSTITUTE_ID`；不能由同一个 visit_id 猜机构。默认 clinical_data/public，homology/graph3_homology。23张已核实表走双源策略，其他已配置表保留 clinical_data 来源，以目标实际主键确认记录身份。源地址和凭据沿用现有配置，不写入报告。

旧的分表 homology 开关与此次总入口开关不同；不要只启用旧开关就认为正式双源写入已生效。正式路径与独立验收脚本共用同一个写入器。

## 自动写入与跳过

- 确认病例坐标、稳定业务编号及药品/病理身份后，新记录自动新增，原记录仅补空字段。本地非空值保留，两源非空冲突逐字段跳过。身份冲突、同源重复业务号、药品/非药品同号整条跳过。
- 剂量、单位、频次、途径等相关字段有冲突时，一组跳过，避免拼出错误用药方案。正文冲突不自动拼接。无法匹配旧检验复合主键时不自动新增。
- homology 独有文书只有 Save 等状态时，不推断为正式有效，列为待确认。验收包仅带入此前用户已确认的 C18 三份输血记录的编号和内容指纹；正文或正式时间改变后确认自动失效。其他待确认文书跳过，不以模板状态替代人工业务确认。
- 目标缺列、超长、不支持类型、JSON或时间异常都记录原因，不截断文本、不静默过滤。缺表/主键、特殊触发器等结构风险会使本次验收在写前停止；脚本不会自动扩表或迁移。
- 计划结束、审核、执行、取消时间各自保存；不转换成实际停止时间。签署时间也不填入记录时间或提交时间。本次不改变质控规则。

## 事务和备份

先只读读取两源，源连接强制 READ ONLY、各自 REPEATABLE READ；两库快照不保证跨库同一时刻。任何必需源表读取失败，均不进入本地写入。

Apply 在本地 SERIALIZABLE 事务内锁定范围记录，先把选定病例/表的原始行、列结构，以及相关 Bundle、visit_index 保存为独立范围备份，落盘后读回并生成 SHA256，成功后才执行 DML。**这是验收范围备份，不是全库 pg_dump**。无 DELETE、DDL、自动覆盖或改医嘱状态。

提交前检查范围内所有行集合和原有字段，发现并发变化、意外写入或数据库约束错误则整次原始表事务回滚。提交后再读回。连接在提交瞬间中断时，报告 `data_committed: null`，需核对后再操作。

原始表提交后，病例索引/Bundle 后处理属于另一阶段，无法与原始表跨阶段原子回滚。后处理失败会明确返回 `data_committed: true`，不能按“全部失败”盲目重复。备份保留供恢复核查；脚本没有自动恢复接口。

正式入口报告 `bundle_refreshed` 表示刷新执行成功，不冒充逐字段验证。独立验收脚本还会从客户机已安装后端刷新8类Bundle并按文书编号、来源表和正文段落读回，返回 `bundle_verified`。

报告区分成功写入、未变、字段冲突、无法映射字段及身份隔离；待处理记录的编号放在单独 `*-review-private.json` 中。控制台只输出数量、路径和安全错误类型，不输出病历原文、SQL参数或凭据。

## 验收范围与命令

工具包：`medqc-dual-source-write-acceptance-20261022.zip`。不覆盖客户机项目代码，读取其 `.env`，从原来配置的医院源库取数，目标仅允许客户机 localhost 的 medqc。

默认只处理 C17、C18、C22，表为住院药品医嘱、非药品医嘱、输血记录、出院记录。一次最多3例。只读预览不写库、不刷新Bundle；Apply 先范围备份再写入。重点核对 C18 三份输血记录和一份出院记录，C17/C22 医嘱独立时间字段。

先复制工具包至客户机 `D:/medqc/`，再执行：

```powershell
Expand-Archive `
    -LiteralPath 'D:\medqc\medqc-dual-source-write-acceptance-20261022.zip' `
    -DestinationPath 'D:\medqc\dual-source-write-acceptance' `
    -Force

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\dual-source-write-acceptance\sync-medqc-dual-source.ps1' `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.4\backend'
```

预览报告确认后，实际验收命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\dual-source-write-acceptance\sync-medqc-dual-source.ps1' `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.4\backend' `
    -BackupDir 'D:\medqc\backups' `
    -Apply
```

有冲突不需要逐条人工批准正常数据；脚本只跳过对应字段或身份不明记录，安全数据照常写入。报告存在 pending 不等于写入失败；结构/连接错误则明确报错。默认不会补齐所有缺失的目标列。

## 已完成验证与边界

- 相关124项离线测试通过，覆盖源端只读、默认预览、备份失败不写、冲突保留、类型和长度约束、并发写保护、重复运行、正式入口路由和后处理失败状态。连接替身用于写入测试，没有写业务PG。
- 用真实27例双库冻结导出和本机只读表结构做23表候选演练；C18可生成3份输血记录和1份出院记录的新增计划。历史快照中的候选数量不代表客户机当前会写入同样数量。
- Ruff、PowerShell语法和差异空白检查通过。客户机实时连接、实际写入和客户机安装版本的Bundle读回仍需上述小范围验收，不宣称已部署验证。
- 未修改医院源库、主工作树、运行环境开关或质控结论；没有重跑27例质控，没有模型调用。

## 客户机已提交后的验收修正

客户机首次 Apply 返回 `data_committed: true`，Bundle验证失败。已在本机只读复现验收器的确定缺陷：`running_record_bundle`、`final_record_bundle` 的文书目录位于 `structured_context.document_inventory`，原验收器直接查询不存在的 `source_documents` 列，得到 SQLSTATE 42703。领域Bundle则有独立 `source_documents` 列。

验收器现按实际列结构读取，增加明确错误代码、阶段和无正文栈位置，并支持 `refresh: false` 的只读确认。旧资料的空正文字符串 `[]` 不作为需匹配的正文；指定的C18四份文书必须实际读到，避免空范围误通过。

修复已用本机现有 C17/C18/C22 的9份输血和出院文书实际只读验证通过，不刷新Bundle、不写库、不调用模型。客户机仍须执行单独的 `confirm-medqc-dual-source-20261022.ps1` 确认实际结果；不应重复 Apply。该独立确认脚本会校验上次范围备份的SHA256，并读取现有Bundle。它不修改客户机项目文件，只在临时目录生成检查器。
