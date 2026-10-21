# 病程签名同步缺口与源端核查

## 本次证据

用户在客户机 Navicat 对 clinical_data 的27例进行了只读核查，查询排除了删除记录，不返回签署人姓名或病历正文。

| 表                          | 有效文书数 | 普通签名列有值                                                      | 普通正文存在签名栏 |
| --------------------------- | ---------- | ------------------------------------------------------------------- | ------------------ |
| daily_course_record         | 186        | physician_sign：0                                                   | 180                |
| senior_course_record        | 344        | recorder_sign、attending_physician_sign、senior_physician_sign：均0 | 336                |
| postsurg_firstcourse_record | 5          | physician_sign：3，分别为C08、C23、C25；surgeon_sign：0             | 5                  |

签署时间列均为空。JSON中术后首次病程的 physician_sign 同样有3份，未发现普通列之外可补用的独立签名；提交人和修改人不等于签名。JSON候选路径中的 normal_sign、abnormal_sign、vital_sign 是体征，不是签署信息。

JSON原始文本中签名栏命中数分别为172、249、5，少于普通正文，不能改成只读取JSON正文。正文签名统计只证明存在姓名形态的签名栏，不证明电子签章有效。

此前本地表结构只读检查证实这三张表均缺签名列，实际 upsert_to_local 依照本地列过滤源字段。故源端现在有值的3份术后首次病程签名存在明确的保存缺口；不能再概括为源端结构化签名全部为空。源端当前值不代表此前历史同步时刻也有相同值，本次未跨库取得逐文书历史快照。

原有正文签名未在Bundle或渲染投影丢失：本地表、领域Bundle、渲染块分别保留180、336、5份。独立 signatures 为空与正文缺失是两件事。

## 修复范围

- 三类本地病程表补11个可空字段：7个签名文本、4个带时区签署时间；保留医师、记录人、主治、上级、术者各自角色，不互相补值。
- 源 physician_sign_time 映射到本地 physician_sign_datetime；seniorphy_sign_time 映射到 seniorphy_sign_datetime，保留时区。
- 常规同步和客户样本同步共用真实写入器：源签名有值却没有目标列时，在写入前明确提示升级，避免继续静默过滤；源空值不制造签名、不阻断旧库。
- Bundle身份元数据补读记录人、上级及其独立签署时间，渲染按原角色传递；不改变10-01-01或04-05-01临床判据。
- Alembic新增20261020_000050，衔接20261016_000049，仅补缺列。split模式只修改本地cdm，single模式使用public。
- 独立客户机脚本供旧R26.4目录使用：只连接本地medqc，读取该目录.env，不打印凭据；事务内补列并回读类型，设置5秒锁等待和30秒语句超时。可重复执行，不修改Alembic版本，不回填原记录。

## 客户机操作

将 scripts/customer-course-signature-upgrade.ps1 复制到客户机 D:\medqc，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\customer-course-signature-upgrade.ps1' `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.4\backend'
```

成功标志为 UPGRADE_OK schema=cdm tables=3 signature_columns=11。升级只补列，不自动补齐已有27例签名；匹配的同步程序部署并重新同步后，才验证源端3份签名的保存结果。后续正常Alembic升级会跳过已补字段，不需手动stamp。

本轮不修改客户或本机业务库，不调用真实模型，不重启服务，不打包。此前正文签名修复及27例两规则54配对离线结果见[正文签名接续卡](2026-10-20-course-body-signature-fix.md)，不将合成同步探针当成真实源库同步验收。

## 验证

相关pytest共309项通过，覆盖真实写入参数过滤、旧库有值签名拒绝丢弃、空值兼容、时间别名、各角色Bundle与渲染传递、模型列、PG迁移DDL和独立客户脚本。在backend目录执行：

```powershell
py -3.10 -m pytest tests/unit/test_course_signature_sync.py tests/unit/test_course_signature_migration.py tests/unit/test_document_identity_metadata.py tests/unit/test_sync_consistency.py tests/unit/test_case_set_sync_service.py tests/unit/test_homology_sync.py tests/unit/test_death_record_sync_content.py tests/unit/test_luxian_0609_course_signatures.py tests/unit/test_luxian_0609_physician_handoff.py tests/unit/test_luxian_0609_postop_audit_regressions.py -q --tb=short
```

Alembic heads确认仅20261020_000050一个head；PowerShell语法解析通过。新增与其余修改Python文件Ruff通过，cdm.py的5项未用导入告警与HEAD一致，无新增。编码检查9个文本文件通过，ESLint只读检查0 error、1489 warning。本机空闲内存约2.2GB，纯后端修改按资源例外不重复前端类型及全量单测；Lint使用相同范围只读检查，避免自动格式化其他会话的文件。
