# 单源候选复审与未来部署前置（本轮不执行现场操作）

此ZIP为源码/构建资源复审候选，不是正式Linux升级包，不含wheelhouse、凭据、患者材料或自动部署命令。运行依赖沿用已验证的Python环境，版本以包内requirements为准；依赖变化须另做兼容检查。

## 可直接复制给复审Agent

请先核对外部`.zip.sha256`、解压后`CHECKSUMS.sha256`、PACKAGE.json的Commit与BASE。不要部署，不连现场或业务库，不启用模型/自动任务。独立目录执行：

```powershell
python -B selfcheck.py
python -B selfcheck.py --test
```

`--test`使用进程级网络护栏、固定夹具和内存SQLite，不读取真实.env。请核对普通列表/详情/文书/新任务固定东华、原库故障不兜底、已登记材料例外、历史授权和原文缺失拒绝。检查063唯一head，排除064及来源共存DDL；审查PATCH和变更清单。PG16集合按包内runner放入Git工作树后，在原有独立CI/网络命名空间执行，不连接5432。报告明确PASS/BLOCKED与限制。

## 正式升级前另行授权后的核对项

1. 核对运行中普通旧来源任务清单，只读报告；本轮不取消、不重试、不改绑、不清理历史结果。未来维护窗口必须防止旧执行进程继续使用原来源。
2. 业务库继续配置DATABASE_URL；CDM连接使用专用只读账号及`CDM_PGPASSFILE`，Linux文件600，目录可由应用账号穿透；禁止使用同步写入账号。不要把秘密写入URL或聊天。
3. 单源模式为`MEDQC_CLINICAL_SOURCE_MODE=fixed_donghua_cdm`（代码默认）；系统设置填写独立CDM主机、端口、数据库和只读用户名，先只读预检，核对全部必需表/列和SELECT权限。停用时允许保存配置但所有普通读请求受控失败；不会切回Homo。
4. 现场业务库低于063时，必须备份并执行正式迁移后核对刷新两表真实schema/owner/序列；已是063则不新增DDL。不得stamp或手建064。保留原业务本地CDM与1026/PDF登记、文件、结果。
5. 核对`QC_CASE_MATERIAL_DIR`或既有dispatch父目录回退是否位于持久数据盘、release之外。普通任务复用已有快照合同；PDF不新增快照。
6. CDM启用前确认受控发布完成窗口及`QC_CDM_CAPTURE_WINDOW_UNTIL`现有门禁；不能用单表更新时间或operation替代全部接口发布就绪。
7. 保持`MEDQC_STARTUP_BACKGROUND_ENABLED=false`、`MEDQC_RESUME_QC_TASKS=false`、`QC_TASK_DISPATCH_MODE=legacy`，不启用旧Homo同步、独立同步任务、定时质控或模型。本轮没有修改现场任何开关。
8. 只读核对1026材料和历史结果页面；普通病历列表只展示东华，未配置时明确失败。跨病例QC分析仍不开放，旧QC汇总不可用时必须明示，不借旧值。

回退须另行授权：停止新应用执行进程，保留业务库/材料/快照/审计表，恢复前一release与配置备份；不降迁移063、不删除数据、不重算历史结果。旧任务是否恢复必须人工核对，不能因回退自动启动。候选包本身没有执行部署的脚本。
