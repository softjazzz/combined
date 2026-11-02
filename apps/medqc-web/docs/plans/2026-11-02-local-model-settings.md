# 本地模型选择与目录管理

## 范围与设计

基线为业务集成提交 `a86da4f0bf708b9d3868f1e7f2d5c2e9c1a5acdc`。
独立工作树 `C:/medqc-local-model-settings-20261102`，分支
`codex/local-model-settings-20261102`。不修改集成分支、不写业务PG、
不连接模型服务、不运行质控。

现有后台已支持Strata及Ollama，但目录只返回部署已启用的服务，导致本机
只配置云端时，本地入口和本地模型管理一起消失。

采用显式“云端API／本地推理”选择，并复用现有服务商／模型选择和保存链。
不新增另一套模型配置，也不将本地服务伪装为云端。API地址和密钥继续由部署提供，
本轮不新增地址或密钥输入框。

## 实现

- `GET /api/v1/llm/local-options` 只对系统配置管理员开放，提供Strata和Ollama
  的本地模型目录，以及逐模型的配置可用性。未配置服务仍可查看；不返回地址、密钥、
  Gateway令牌或profile名称，不查询远程模型列表。
- 未启用的本地服务也允许管理员登记／删除实际模型ID，复用既有自定义模型JSON目录。
  保留模型名大小写及Provider隔离；登记不下载模型、不启用推理、不改当前生效配置。
  云端未启用Provider继续拒绝新增。旧providers/models接口的运行可见性不变。
- 目录与Strata保存入口共用本地运行配置校验，保留显式启用、API与模型、Gateway、
  逐模型profile及角色覆盖限制；Strata缺Gateway地址或令牌同样拒绝。
- 本地模型即使与云端内置名称相似，也不再被云端别名解析改成小写；保存、读取及
  运行加载均保留完整原名，云端已有别名合同不变。
- 未配置服务／未映射模型可以选择查看和管理名称，但不能保存成当前服务或测试连接。
  配置可用不代表服务存活或医学质量通过；连接测试明确提示会实际请求模型。
- 本地目录读取失败显示错误，不能当作真实空目录；云端选择保持可用。
  成功的模型目录修改不自动保存配置。切换服务时迟到的目录／新增响应不覆盖当前草稿。

## 验证

```powershell
# 后端：OfflineIsolation阻断真实网络、.env、业务PG及任意子进程。
Set-Location C:/medqc-local-model-settings-20261102/apps/medqc-web/backend
py -3.10 -B scripts/run_qc_scheduler_tests.py --profile offline `
  tests/unit/test_strata_admin_configuration.py `
  tests/unit/test_llm_config_permissions.py tests/unit/test_llm_config_loader.py

# 前端：Node传输层阻断TCP/TLS，服务应答使用固定替身。
Set-Location C:/medqc-local-model-settings-20261102/apps/medqc-web
node --require ./scripts/frontpage-v2-no-network.cjs ./node_modules/vitest/vitest.mjs run `
  tests/unit/components/LLMApiConfigStrata.spec.ts `
  tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts
npm run type-check
node ./node_modules/eslint/bin/eslint.js src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --no-fix
npm run check:encoding
```

后端73通过，前端定向32通过，完整类型检查通过，相关Ruff通过。
全src只读ESLint无错误，仓库已有样式警告保留，不为此修改其他页面。
浏览器使用真实组件与独立合成目录检查：本地入口、多个模型、未就绪提示及禁用按钮。
预览没有认证生产账号、访问PG或调用模型；没有将合成状态冒充部署结果。

完整前端隔离回归：198文件通过、1文件失败；1954项通过、1项失败。
失败为既有 `workstation-report-adaptation.spec.ts` 的旧19项导航断言，
实际因已合入的首页V2入口为20项。本批未改导航或该测试，另在未修改的
`a86da4f0b` 集成工作树以相同网络隔离入口复核，不以修改旧断言强行通过。
相关修改文件ESLint零警告；全src只读ESLint为零错误、既有警告。

## 发布及回滚边界

不需要数据库迁移；本轮不修改.env、当前保存的Provider／模型、Prompt、医学规则、
结果合同、Gateway资源容量或冻结协议。普通账号仍不能访问或修改本地目录。
默认云端路径保留。本地服务须由部署人员配置启用后，再由管理员明确选择并保存。
保存失败不允许隐式回退到云端。未做任何真实模型／网关连通性、医学质量或吞吐验收。

回滚本批代码即可恢复原目录及页面；已登记的自定义模型沿用原JSON格式，
无需删除模型名称或修改业务库。

## PR28 CI复核收口

原Head `9d2bfd424` 的调度隔离、M2一次性基础设施和零模型质量门均通过，
其中零模型门11961通过、0失败、0超时。但原触发器没有覆盖本批前端文件，
调度CI也没有运行模型配置的73项合同，不能以原三门绿代替本批验收。

补齐前端模型组件、服务、配置页面及相应测试路径触发；同一工作流新增
本地模型配置及导航兼容测试。后端调度工作流显式增加本地目录、保存/加载、
权限3文件。新步骤同时保留OS网络命名空间和原进程级隔离，不使用业务PG或模型服务。

隔离反例额外确认并修复两项边界：

1. Ollama启用但API地址为空时，目录报未就绪，直接保存却可成功。
   保存、测试与目录现共用本地校验；失败发生在构造模型客户端之前。
   合法的直连Ollama仍可保存，不强制它经过Strata的Gateway。
2. 非空但过短或全空白的Gateway令牌可被目录误报就绪。
   现直接复用实际Gateway出口的纯配置校验，覆盖令牌、URL和profile身份；不发HTTP。

上述3个参数化反例在修复前全部失败；修复后后端3文件**77通过**，
前端模型/配置页面/导航3文件**41通过**；完整类型检查、相关Ruff和只读ESLint通过。

旧导航失败已仅在测试中收口：保留原19项并显式加入已合并的首页V2入口，
继续断言完整顺序，并增加首页V2路径和实际路由名。未改产品导航或Layout。
该文件现9项通过。本轮未重复全量前端；此前1954通过/1失败为修复前历史记录，
不能改写为本轮全量通过。

新Head CI结果以PR28最新Actions为准；本轮不重启当前9d2bfd424只读服务、
不移动业务集成线、不写库、不调用真实模型、不运行患者质控。
