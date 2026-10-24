# 五类材料与失败结果收口 Implementation Plan

**Goal:** 在独立同步分支交付五类材料固定验收和原任务失败项定向恢复工具，保留成功结果，不重跑27份。

**Architecture:** 复用现有双源归一化、实际 Bundle 组装、规则 Source Reader、发布保存及失败配对合并 owner。材料验收默认只读；恢复默认预览，匹配任务三坐标和规则、材料与已录应答，备份后才定向写入。缺源连接、缺字段、提示词不匹配必须明确阻断，不能报零或假通过。

**Tech Stack:** Python 3.10、PostgreSQL、SQLAlchemy、现有 LX0609 owner、Windows PowerShell 5.1。

---

## 已确认约束

- 工作树 C:/medqc-qc-source-fixes，分支 codex/qc-source-completion-20261023；集成分支不变。
- 五类为输血、出院、医嘱时间、病理、签名；签署时间不能冒充记录/提交时间，计划结束不能冒充实际停止。
- 所有患者原文及坐标留 .tmp/0910-full-audit/ 的 -private 文件，控制台仅样本别名和计数。
- 优先复用已有应答；本轮默认禁止真实模型 HTTP。不能匹配时返回明确阻断，不自动换材料或改答案。
- 正常结果不得重判或覆盖；恢复仅允许原 failed_records 中的配对。

### Task 1: 固定材料验收

**Files:** 新增 backend/app/services/qc_workspace/material_chain_acceptance.py、backend/scripts/verify_p0_material_chain.py；测试 backend/tests/unit/test_p0_material_chain.py。

1. 写反例：源有正文/时间/诊断/多人签名，但本地或 Bundle 或规则投影缺字段，必须标明丢失层。
2. 运行聚焦 pytest，确认反例能失败。
3. 五类统一记录按三坐标+表业务主键比较，复用双源 normalize_row；比较已保存 Bundle 与原生/快照规则读取。正文冲突不自动覆盖，结构化时间独立比较；签名完整保留名单，不猜角色。
4. 覆盖缺表、查源失败、空样本集、重复业务键、来源有值但目标为空、旧投影遗漏、目录截断、真实无值、时间语义混用。
5. 使用1022现有资料与冻结源做离线/只读验收；冻结源结果不能冒充客户机实时源验证。

### Task 2: 失败配对恢复

**Files:** 新增 backend/app/services/qc_workspace/offline_failure_recovery.py、backend/scripts/recover_p0_failed_results.py；测试 backend/tests/unit/test_p0_failure_recovery.py。仅必要时扩展现有 custom_qc_workspace_service 的保存 owner。

1. 写反例：范围外/重复/不交付状态/材料不匹配/任务并发改变/备份失败全部拒绝。
2. 复用 failed_rule_retry.merge_failed_rule_retry_results，精确选择原失败配对；已有成功记录逐项相等。若同任务已有成功结果，保留，不从其他任务跨版本搬用。
3. 已录应答逐字提示词匹配，经原执行器、发布与保存合同后才作为候选；不调用模型、不放宽 Finalizer。
4. 默认预览；Apply先备份，事务锁/CAS再保存，并从 Canonical 读取与导出复核。保持其他任务、既有成功结果和无关信封不变。
5. 本机仅用隔离测试验证写入；业务库只读，不自动恢复本机历史任务。

### Task 3: 客户工具包及交付

**Files:** 新增 scripts/accept-medqc-p0.ps1 及最小资源打包；更新此文及 PROJECT_ROLLING_TODO.md。

1. 读取指定 backend/.env，不显示口令、不沿用其他目录配置。
2. 预览检查安装源码/运行源码一致；需要安装的修复先源码备份，仅接受已知版本，不覆盖未知修改。
3. 输出完整PowerShell命令、报告与范围备份路径；客户机执行前只称“工具已完成”，收到执行及恢复读回证据后才能关闭客户P0。
4. 定向测试、Ruff、PowerShell语法、编码、ZIP资源校验；不跑前后端全量。

## 本轮交付与实际证据

1. 五类材料的固定验收覆盖9张表：输血记录/申请、出院记录、药品/非药品医嘱、病理、日常/上级查房/术后首次病程。按机构、患者、就诊及业务键，逐字段比较双源、本地PG、已保存Bundle、原生及快照规则读取。源表不可用、冲突、缺字段与真正零行分开报告。声明为非证据的展示目录上限，仅在两种真实规则读取都完整时归为展示省略。
2. 修复出院分节组装丢掉完整正文/JSON的缺口，独立保留签署时间；不能填成记录或提交时间。医嘱四个时间独立保存/读取，计划结束不冒充实际停止。
3. 签名补空只接受同编号且去空白后正文主体完全相同、明确末尾签名、无已有角色签名的记录。保留多人名单，不按位置猜角色；正文变化或双源名单冲突仍跳过。
4. 失败恢复通过真实Worker、发布与保存owner重放已录应答，提示词必须逐字唯一匹配。只允许原任务的C15/07-04-01、C18/07-01-02；本次实时材料验收必须同1022三坐标范围且不超过30分钟，目标病例的两张输血和两张医嘱表均通过。无网络回退，不创建新质控任务。
5. 保存前备份原任务及信封，事务锁内核对旧基线；原成功items逐项保持，未恢复失败项保持，其他病例信封原行保持。只为已补齐病例重新发布信封，随后通过正式读取及CSV/XLSX导出合同验证。
6. 客户安装器仅替换已知版本的指定AST节点及新增模块，整批预检、源码备份、编译后写入，未知修改拒绝覆盖。运行时证明比较已加载函数与磁盘编译结果，保留原发行包build_id。只重启8001后端，使用已有验收启动模式，禁止启动旧质控队列；不停止PG或前端。

### 本机验证

- 两组聚焦测试139+148=287项通过，包含隔离SQLite真实保存事务的范围、回滚及并发基线保护。相关Ruff、PowerShell语法和迁移资源校验通过；未运行前端全量、后端全量或真实模型。
- 在实际R26.5包源码上安装12个文件，未指定函数AST不变，重复安装通过；补齐包内静态规则资源后实际导入及已加载函数证明通过。此演练不启动HTTP服务、不连接业务PG。
- 本机1022与已有双源冻结导出完成27例只读固定验收。医嘱时间及病理的实际原生/快照取数通过；C18三份输血和出院记录已有材料链通过。冻结导出没有blood_application表，因此不能据此宣称申请材料或客户机实时源通过。
- 还发现出院JSON15份、独立签署时间10份源端有值而本地缺值；存量Bundle中完整出院正文/JSON亦有缺口。签名6份源端有值而本地缺失，另有两份源端单侧文书。此处是缺口盘点，并非全部允许自动补数。
- 使用真实归一化/写入规划/Bundle组装/规则字段声明只做内存演练：可安全补入出院JSON14项、签署时间9项、签名1项，共24项；其余维持冲突或有效性待核实。未写入本机业务库，未刷新本机存量Bundle，未重启本机服务。
- 集成工作树保持原分支和HEAD，没有将本轮代码合入或写入该工作树。客户机实际源验收、补数和原任务恢复尚未执行，两项客户P0不能提前标为关闭。

## 客户工具包和完整命令

交付包：`medqc-p0-closeout-v2-20261024.zip`，SHA256：
`0286f53ba588263e5f8b076b9add81f470ad00a707dc613299d1275396d87cf3`。

将包复制到客户机D:/medqc，执行：

```powershell
$ErrorActionPreference = 'Stop'
Expand-Archive `
    -LiteralPath 'D:\medqc\medqc-p0-closeout-v2-20261024.zip' `
    -DestinationPath 'D:\medqc\p0-closeout-v2' `
    -Force

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\p0-closeout-v2\accept-medqc-p0.ps1' `
    -Mode Closeout `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.5\backend' `
    -BackupDir 'D:\medqc\backups' `
    -OutputDir 'D:\medqc\p0-closeout-reports' `
    -RecordingDir 'D:\medqc'
```

Closeout先只读排除近期活动质控，完整备份并升级到053、源码备份安装、验证后端实际加载，然后分批备份补空并刷新Bundle、实时只读验收、离线预演及备份后恢复失败项。应答扫描仅寻找既有`*-calls-private.json`，不读取凭据给模型，不将应答/病历装进工具包。

成功结果不重判；源端单侧Save文书没有既有确认时仍待核实。任一安装未知修改、材料断链或提示词未匹配均明确停止。全局其他材料存在缺口但目标失败病例通过时允许独立恢复目标失败项，最后仍报告材料P0未关闭；若只恢复了部分失败项，保存后明确返回未完成，不能用退出成功冒充全部收口。发生停止时查看`data_committed`和阶段，不能盲目重复写入或改跑27例。

操作会重启后端；验收模式保持旧质控队列自动恢复关闭。客户返回材料通过及恢复读回/导出成功的安全事件后，才可关闭对应P0。源端、客户PG及私有应答原文无须贴到聊天。
