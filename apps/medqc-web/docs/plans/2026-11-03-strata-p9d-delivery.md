# P9-D：真实计量接入与DSH隔离验收

本包只用于DSH的虚构病例联调，不是生产升级包。开发侧不连接模型服务，不运行患者质控。不能用本次Mock回归证明模型医学质量、服务器容量或全引擎16K兼容。

## 版本和依赖

- 业务基线：`d063761e544b4bb6d95892c9802f2edf84f47203`。
- PR31尚未合入；明确引入P9-B提交`abe9eba0f`，本分支对应`ce79c401a`。
- 实际完整Commit以包根`build-info.json`为准；前端`frontend/dist/build-info.json`应相同。
- 本轮没有新增迁移。普通产品UI需要既有062；CLI虚构病例使用自己的SQLite，不需要PG，不会迁移PG。
- 没有推送、合并或修改业务集成分支。

## 实际DSH交付与信任边界

已找到`Downloads/ab-2026-10-30/provider-handoff`，实际14个文件（不含生成缓存）。原计量器是标准库Python实现；资源与原始向量逐文件SHA256固定在`backend/config/strata-qwen36-p9c-approved.json`。不自行重写分词算法、不修改期望Token数。

原始17项文本向量和17项单User完整消息向量离线验证。五种消息序列来自DSH正式能力合同：`user`、`system/user`、`user/user`、`system/user/assistant`、`system/user/assistant/user`。交付声明的13次服务器比对不是开发机重新执行的API验证；也不能将此前口头20/20当成现有17项序列化向量。

Counter、模型、Tokenizer和模板版本严格匹配；所有资源先核验再加载，Runtime仅初始化一次，计量串行保护，关闭时只注销自己的注册。工具、多模态、未知角色序列及strict json_schema不放行。必要输出上限不缩减，仍要求：输入＋最终输出上限＋64 ≤ 16384。

实时身份核对严格使用交付中的`/v1/models`与`/health`，检查准确模型ID、loaded状态和16384 Context；不猜`/props`。两项GET均需鉴权。短缓存60秒，端点和密钥身份隔离，失败不POST。不把响应model回显当身份认证。GGUF权重/引擎的远端真实文件哈希仍由DSH服务器侧核验，GET不能独立证明它们。

`integration_example.py`只作为交付原件留存以核验哈希，**不要运行**：其中注册接口与当前应用不同，且含不适用的输出缩减示例。本应用只加载固定哈希的`token_counter.py`。

## 行为和回滚

- Qwen3.6目标模型必须使用完整Greedy、Thinking OFF、身份及精确预算保护，不能用全局P5-B开关关闭来绕过。
- 百炼和未显式选择P9协议的旧Qwen3.8 Profile保留旧行为。
- Direct和Gateway均在实际发送前计量；恢复/去除不支持的JSON模式后重新计量。Context、length、structured_output_failed均是技术失败，不转换成临床资料不足；其他400/502不盲目归类。
- `draft_n=0`只观测。固定探针报告draft字段，不要求生产业务每次大于0。
- 未更改临床Executor、时限、医学Prompt或发布状态合同。使用原P5-B安全拆批及同族成功保留；不完整不冻结为成功。
- 回滚：停止独立进程，保留`isolated-state`审计，恢复原部署入口即可。没有覆盖正式程序或DB。应用功能回滚可选择原百炼／旧模型Profile，不改医学数据。

## DSH完整PowerShell操作

使用新的目录，例如`D:\DSH\P9D`，不要解压覆盖现有部署。先核对开发交付的ZIP SHA256，再展开；以下将`$pkg`指向解包后的包根。

```powershell
$archive = Read-Host '输入收到的P9D ZIP完整路径'
if(-not (Test-Path -LiteralPath $archive -PathType Leaf)){ throw 'ZIP不存在' }
Get-FileHash -Algorithm SHA256 -LiteralPath $archive
$destination = Read-Host '输入全新解包目录，例如D:\DSH\P9D-new'
if(Test-Path -LiteralPath $destination){ throw '目标已存在，请选择新目录，不覆盖' }
Expand-Archive -LiteralPath $archive -DestinationPath $destination
$roots = @(Get-ChildItem -LiteralPath $destination -Directory |
  Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'build-info.json') })
if($roots.Count -ne 1){ throw '包根目录数量异常' }
$pkg = $roots[0].FullName
Get-Content -LiteralPath "$pkg\build-info.json"
& "$pkg\runtime\python.exe" -c "import sys; print(sys.executable); print(sys.path)"
& "$pkg\tools\p9d-isolated.ps1" -Mode Verify
```

Verify不连接API，验证包内真实资源与17项消息计量。失败则停止，不手工修改verified或期望值。

DSH另开一个PowerShell窗口建立既有SSH隧道，替换SSH账号和服务器名；本机18084必须未被占用：

```powershell
$sshTarget = Read-Host '输入DSH已确认的SSH目标，格式user@host'
if([string]::IsNullOrWhiteSpace($sshTarget)){ throw '未提供SSH目标' }
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18084:127.0.0.1:18083 $sshTarget
```

回到验收窗口，口令只放当前进程，不写配置文件：

```powershell
$secret = Read-Host 'Strata API Key' -AsSecureString
$env:P9D_STRATA_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
& "$pkg\tools\p9d-isolated.ps1" -Mode Probe -Endpoint 'http://127.0.0.1:18084/v1'
# 核对probe.json：身份及预算通过、结束正常、draft字段已观测。
# 以下才会运行一份固定虚构病例的全目录正式执行链，可能产生多次真实请求。
& "$pkg\tools\p9d-isolated.ps1" -Mode Run -Endpoint 'http://127.0.0.1:18084/v1'
Remove-Item Env:P9D_STRATA_API_KEY
```

Run是明确的现场真实调用步骤，开发机没有执行。它不接受患者文件，不读客户材料，不使用业务PG；只在新UUID目录保存虚构材料对应结果。全目录使用当版正式目录，不硬编码49或强行要求全部规则成功。未满足16K的必要调用应显示技术未完成。虚构材料不含所有临床场景，不能据“不适用”数量判断模型覆盖率。

查看与导出：

```powershell
$run = Get-ChildItem -LiteralPath "$pkg\isolated-state" -Directory |
  Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'report.json') } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $run){ throw '没有完成的Run，先检查该次终端错误和requests.jsonl' }
Start-Process -FilePath (Join-Path $run.FullName 'report.html')
Get-Content -LiteralPath (Join-Path $run.FullName 'report.json') -Raw
Get-Content -LiteralPath (Join-Path $run.FullName 'requests.jsonl')
# 独立导出本次虚构病例及安全调用元数据，不打包其他业务目录。
Compress-Archive -LiteralPath $run.FullName -DestinationPath (Join-Path $pkg ('DSH-P9D-audit-' + $run.Name + '.zip'))
```

审查`results`、`saved_results`、`persistence_failures`和`metrics`；`results.sqlite`使用原Canonical保存器并回读核对状态、原因、事件事实，技术失败留在审计而非医学成功结果。`requests.jsonl`记录每次尝试、Token和耗时；`safe-model-metrics.log`记录最终参数、预算和draft等观测，无Prompt和原答。初次输入/补核/恢复均有独立观测。身份失败的GET与真正模型POST不是同一种请求。

## 可选的产品前后端查看

CLI是本轮主要模型业务链验收入口，并不等于已经验收网页登录、MQ、定时任务或PG写入。包附带同Commit新编译的产品前端和后端；若要查看普通产品页面，DSH必须自行准备**全新本机隔离PG**，名称强制`p9d_*`，禁止指向已有业务库。

```powershell
# 用现场已安装的PostgreSQL客户端创建全新空数据库。-W会交互输入本机PG管理员口令。
createdb -h 127.0.0.1 -p 5432 -U postgres -W p9d_smoke_20261103
# 若DB已存在，停止并改用新的名称，不复用旧库。
$dbSecret = Read-Host '隔离PG账号口令' -AsSecureString
$dbPassword = [System.Net.NetworkCredential]::new('', $dbSecret).Password
$env:P9D_ISOLATED_DATABASE_URL = 'postgresql://postgres:' + [Uri]::EscapeDataString($dbPassword) + '@127.0.0.1:5432/p9d_smoke_20261103'
& "$pkg\tools\p9d-isolated.ps1" -Mode Migrate -AllowIsolatedDatabaseMigration
& "$pkg\tools\p9d-isolated.ps1" -Mode Backend -BackendPort 8019
# 另一窗口（从同一个$pkg路径运行）
& "$pkg\tools\p9d-isolated.ps1" -Mode Frontend -FrontendPort 3109 -BackendPort 8019
```

页面`http://127.0.0.1:3109`。使用acceptance启动避免create_all、预热、自动恢复旧任务；不启动Publisher、Worker或同步服务；新数据库没有定时计划。没有自动创建账号或写入病历，网页账号/完整功能验收需DSH在该隔离库另行准备。不得拿正式管理员凭据或正式数据库来补这个步骤。该可选PG/UI流程开发机未执行；本次没有声称它已验收。主要验收病例已由CLI固定导入到请求内材料，通过正式执行链运行和独立保存，无需在网页重复质控。

停止方式：运行中的前端、后端和SSH窗口分别Ctrl+C；不停止其他进程、不删除数据库或旧程序。保留本次审计，关闭窗口或移除该窗口中的P9D环境变量。

## 16K适配范围和限制

- 受保护：目标Qwen3.6的Direct、Gateway、首答及恢复；缺资源、身份不符、无法计量、形态未验证、预算超限均拒绝发送。
- 已有安全拆批：P5-B检查族共享抽取、06-01-04专项配对及补核，事件/文书ID和比较上下文沿用原边界，局部否定不能证明全窗缺失，早期失败/晚期成功不能制造确定超时。
- 仍不兼容：必要输出继承16384时，加任何正输入和64余量均无法在16K执行；未安全拆批的会诊、病程、扩展文书，以及单事件仍过长的输入会保留技术未完成。不静默截正文、不用摘要替代、不min缩输出。
- 工具、多模态、strict json_schema和未验证角色序列不支持；大于16K的Context没有实测合同。
- 实时GET身份、服务端usage对齐、真实恢复、Windows现场SSH及虚构病例模型结果须由DSH执行，不在Mock通过范围内。

## 开发验证记录

本轮定向结果与最终Commit记录在工作树交付汇报；重复测试不相加。原DSH验证脚本17/17通过；真实Counter向量通过；Mock Direct/Gateway完整参数、身份失败、预算、结构化失败恢复、draft=0，以及百炼和旧Qwen3.8回归使用严格offline入口。虚构全目录固定无效模型协议验证确定性成功仍保存、技术失败不当作合规。包内Runtime另做真实资源计量验证。

扩大去重离线回归1017通过、2项私有原报告入口跳过；包白名单17项通过；另用真实Counter＋正式客户端＋Mock HTTP贯通虚构全目录执行和内存Canonical保存，确认不改原输出要求也有实际可发的模型调用，继承16384的超限请求被拒绝。后续定向重复不与扩大集相加。完整类型检查通过，Ruff、编码及凭据扫描通过；只读ESLint为0错误、3403项基线警告。

最终P9-D聚焦集139项通过、0跳过，包含真实交付17项向量、完整客户端与虚构全目录的内存保存闭环、打包白名单；与上述扩大集重叠，不相加。

首次包内启动检查拦截了隔离入口对旧`get_settings.cache_clear()`接口的误用，已改为当前环境快照机制，补启动回归20项通过。独立Python关闭自动site加载，包内验证要求所有模块搜索路径都留在包目录；不继承开发机用户包或执行`.pth`文件。实际依赖版本保存在`requirements-runtime-lock.txt`。首次失败的试装目录不作为交付包。

包内固定应答自检使用当版完整可选目录90项（含扩展范围），故意返回无效模型协议：58项可交付结果经Canonical保存读取一致、32项保留技术未完成，真实模型请求0次。此自检不是90项医学验收，也不代表所有49条正式规则都调用了模型。打包源码必须保留`app/services/qc_diagnostics`，仅排除`app/storage/qc_diagnostics`运行资料；包白名单回归覆盖这个区别。

全量前端单测、业务PG迁移、真实API压力测试及真实病历质控未执行。DSH现场通过前不自动启用Qwen3.6，不覆盖正式部署。
