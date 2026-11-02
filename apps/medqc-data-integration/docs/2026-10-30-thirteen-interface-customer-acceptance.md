# 十三接口客户机验收收口记录

状态：**0.3.2真实接管与部署验收通过，尚未正式启用定时任务或切换业务数据源。**

依据为用户回传的DSH客户机执行结果；开发机未重新连接客户数据库或读取病历。
开发机复算的交付包完整SHA256及两份脚本SHA256与回传信息一致。
本记录不重新打包已验收版本，不改变其82项校验值，也不增加接口。

## 固定交付与现场

- 范围：已有13接口，Caché → 原始层/历史 → 正式CDM发布器。
- 客户环境：真实Caché、PostgreSQL16.13、Python3.10.11 x64、InterSystems ODBC35 x64。
- 发布代码提交：`61072e6f72547d3d62030e6234e28db67f744560`。
- 服务目录：`D:\medqc\service-takeover-0.3.2`。
- 运行目录：`D:\medqc\service-takeover-run-20261030205035`。
- 统计报告：运行目录的`reports`，DSH报告共17个JSON；原始文件留客户机。
- 接管库：`medqc_ingest_takeover_20261030205035`。
- CDM库：`medqc_cdm_takeover_20261030205035`。
- 恢复库：`medqc_restore_takeover_20261030205035`与`medqc_restore_takeover_20261030205036`。

交付包：`cache-service-source-validation-0.3.2-20261030.zip`，187,737字节。

```text
ZIP SHA256
bf75adaf388fccf0dc56ce78de15efece3c4b6dc8716237a77dfca145baa930b

deploy/windows/resume-source-validation.ps1
5a008e1f54bb9e8df9acfd70d55c6385f5489d5d977de46256e9d9ecd9acc5fb

src/medqc_ingest/adapters/cache.py
95cd89db2bc97200b01795809c624a64d814215b9fd16d7d9220a194ce1f2577
```

## 已通过的六项验收

| 项目 | 客户机证据 |
| --- | --- |
| 接管完整性 | 初始87,201条raw及87,201条历史、5项原始归档核对通过；导入已提交 |
| 两轮发布 | 真实源回放后13接口两轮changed均为0；选中87,227行，逐字段一致 |
| 故障恢复 | 提交前注入回滚、失败审计和恢复均通过，恢复41条unchanged，checkpoint未推进 |
| 真实源读取 | 13接口2026-10-28 dry通过；前后ingest全表/序列指纹一致；replay新增26、更新1,218 |
| 备份恢复 | ingest/CDM分别恢复到既有空恢复库；表内容与序列指纹逐项相同 |
| 原库保护 | 成功报告、运行配置、原始归档及checkpoint未改；正式业务库未连接；PG服务未改 |

最终`deployment-result.json`：`accepted`、`interfaces=13`、`service_version=0.3.2`、
`archive_preserved=true`、`rollback_recovery=true`、`backup_restore=true`、`cache_accessed=true`、
`completed_stages_repeated=false`、`business_database_accessed=false`。

源克隆库迁入使用部署身份的只读连接，未给源库补授权；运行身份仍为`medqc_sync`。
故障注入留下的失败审计是已验证证据，不能将其当作未处理故障而清理。

## 当前运行边界与下一次上线操作

日任务、首页60日滚动任务XML已生成，默认禁用且未注册，入口指向0.3.2。
已有`MedQC-R22-AutoStart`任务未触碰。PG开机保障尚未修改，不能称为无人值守运行已上线。
完整规则引擎与模型没有执行，正式MedQC业务库/数据源没有切换。

本阶段至此完成，不再补跑已通过项目，也不继续其余42接口的接入。
后续正式启用集中处理：落实共享PG开机保障，注册/启用既有日周任务，核对首个实际调度结果。
业务数据源切换与完整规则验收单独安排；未获明确启用指令前保留现状。
