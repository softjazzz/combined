# 超级管理员推理连接配置

基线：远端 `github/codex/business-agent-integration` 的 `e1f65ffe73f121842dfa997c41d1c9c517bd804e`。
独立工作树：`D:/MedQC-worktrees/llm-endpoint-admin-20261111`；分支 `codex/llm-endpoint-admin-20261111`。

## 行为与范围

系统配置 → 模型配置增加“推理服务连接”抽屉。仅 `sync_admin`、`super_admin` 可读取或修改连接信息，后端独立校验。普通管理员仍可按既有权限选择模型，不可管理密钥。

支持百炼、DeepSeek、SiliconFlow以及本地OpenAI兼容服务/Ollama的直连地址、密钥及启用状态。地址为服务根地址（可含 `/v1`），不包含账号密码、query令牌或fragment；模型ID沿用既有模型选择及本地模型目录。

受控Gateway（含Strata）保留部署管理：页面明确只读，后端拒绝保存覆盖配置，不能通过本功能绕过profile/协议/路由限制。此轮未实现Gateway管理或模型服务安装启动。

保存与测试连接完全分开；保存不访问推理服务，不创建质控任务，不连业务库。测试仍由原模型配置页面显式触发。本轮所有验证均未调用真实模型。

## 持久化、密钥与并发

采用独立文件配置，复用已安装的 `cryptography`，不新增数据库迁移。读取无覆盖配置时不创建文件，保持原部署配置。

目录按下列顺序解析：

1. `LLM_ENDPOINT_CONFIG_DIR`（支持环境变量及现有Settings配置加载）；
2. `QC_DISPATCH_STATE_DIR` 的父目录下 `llm-endpoints`；
3. 开发兼容路径 `backend/data/llm-endpoints`。

生产应使用release之外的持久目录，各API/Worker进程共享同一目录。首次保存按需创建目录、Fernet密钥文件及配置文件；POSIX目录0700、文件0600。Windows仍需沿用运行账号目录ACL。备份必须同时保留 `key` 与 `settings.json`，不得把密钥文件提交Git、放入公开发布包或发到聊天。

API只返回 `key_configured`，不返回明文或密文。新密钥后端加密；留空保留当前密钥；首次从部署切换且留空时保存原有效部署密钥的加密副本。显式清除不回退部署密钥；云端服务需先禁用或填写新密钥才可保持启用。“沿用部署配置”是单独的明确操作，不改 `.env`。

跨进程文件锁 + 原子替换 + 乐观版本冲突409防止并发覆盖。配置与审计在同一文件原子更新；审计记录操作者、时间、服务、启用及密钥操作种类，不记录密钥值。损坏配置/密钥解密失败明确失败，不默默换端点。

## 在途任务、冻结与历史

新服务接纳检查连接配置版本，版本变化时替换服务对象，不就地修改已经运行的客户端。默认、裁决、用途角色、旧调用点角色均从已取得的连接快照构造；密钥只存在服务内存/加密配置中，不加入模型身份或临床结果。

原有端点指纹继续生效；新覆盖配置的版本还进入默认/用途/旧角色模型身份，同地址换密钥也不会复用旧身份冻结。未使用覆盖配置的旧身份保持兼容。旧冻结文件不删除、不覆盖；历史结果查看和保存合同未改。排队/恢复任务继续遵守已有模型身份不匹配即拒绝的合同，不承诺跨进程恢复后继续用过时连接。

## 必要验证

后端使用 `scripts/run_pr8_offline_tests.py`，阻止dotenv、外网和非SQLite数据库连接；配置、加密密钥、合成冻结都在临时目录。

新增HTTP夹具 `tests/fixtures/llm_admin_offline.py` 仅供显式插件加载，不进入应用lifespan，不启动后台作业。首次直接运行旧HTTP测试因禁网入口隔离父conftest而缺少client夹具，不能计为产品失败；补此夹具后相关集合119项通过。随后补并发写、损坏密文、新任务服务替换，新增保护文件20项通过；其中冻结验证写入旧合成冻结，新连接未命中，旧客户端仍命中且旧文件字节不变。

命令（从 `apps/medqc-web/backend` 执行）：

```powershell
python -B scripts/run_pr8_offline_tests.py -p tests.fixtures.llm_admin_offline tests/unit/test_llm_endpoint_settings.py tests/unit/test_llm_config_loader.py tests/unit/test_llm_task_roles.py tests/unit/test_strata_admin_configuration.py tests/unit/test_llm_config_permissions.py -p no:cacheprovider
```

前端定向文件：`LLMEndpointSettings.spec.ts`、`LLMApiConfigStrata.spec.ts`，共16项；覆盖权限入口、抽屉按需读取、保存密钥清空、冲突不重试、Gateway只读、原模型与用途选择。旧测试仅更新启用来源文案及隔离子组件，没有放宽权限/路由断言。

```powershell
node node_modules/vitest/vitest.mjs run tests/unit/components/LLMEndpointSettings.spec.ts tests/unit/components/LLMApiConfigStrata.spec.ts --config vitest.config.ts
```

前端严格定向类型检查（新组件及服务）、相关ESLint和后端Ruff F检查。node_modules使用既有工作树的目录联接，未安装依赖。

最终差量复核：新增连接保护文件20项、用途角色保护25项，合计45项通过；新增抽屉4项及严格定向类型检查再次通过。上述数字有重叠，不累加为全量验证。ESLint无错误（测试替身保留组件数量等风格警告）；后端除 `sichuan_qc_service.py` 原有7项Ruff F告警外其余修改文件通过，该7项已用基线源码逐条比较code/message完全一致，未扩大修改旧逻辑。

未执行：真实服务连接测试、真实浏览器现场验收、生产凭据写入、Linux文件权限现场验证、远端CI、全量测试、部署、27份病历重跑。此轮仅本地提交，不推送/合并。
