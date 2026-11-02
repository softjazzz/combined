# 百炼35B-A3B后台选型接入

## 行为

后台现有模型设置增加`阿里云百炼 / Qwen3.6-35B-A3B`，实际API模型名为`qwen3.6-35b-a3b`。Flash和已有模型保留，默认模型不变，不自动启用双模型级联。

沿用现有页面和`/api/v1/llm/models`目录；前端无需另一套模型列表。管理员选择后保存，页面仍通过现有reload-config入口重载。地址和密钥由部署配置提供，无迁移，无业务库修补。

## 正式调用一致性

原正式LX0609使用adjudicator_client，环境`LLM_ADJUDICATOR_MODEL`可能覆盖后台选型。新保存的百炼配置由保存owner增加布尔控制字段`custom_parameters.qc_use_selected_model=true`；加载owner据此让正式质控与所选模型一致。该字段不进入上游模型请求。

未重新保存的旧配置及纯环境配置保留既有裁决覆盖行为；Strata/Ollama及显式调用点角色覆盖保持原逻辑。普通账号权限不变，保存仍要求原管理权限。手动选择35B是普通服务商/模型切换，不依赖06-01-04实验路由或新比较Prompt。

如果使用Gateway，部署者需在原注册表中配置35B模型对应profile；应用侧`LLM_GATEWAY_PROFILES`同时登记35B与Flash各自profile，Gateway注册表的profile.model必须与所选API模型名一致。复用现有百炼端点/凭据，不借Flash的固定模型profile冒充35B；缺部署映射仍按现有校验失败关闭。direct模式沿用百炼部署端点及密钥。此次未修改实际环境、注册表或运行服务。

## 最小验证

```powershell
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline `
  tests/unit/test_strata_admin_configuration.py `
  tests/unit/test_llm_config_loader.py `
  tests/unit/test_llm_config_permissions.py
```

61项通过。新增两项覆盖目录保留Flash/新增35B，以及管理员保存→加载→双方客户端重建→正式裁决客户端→Gateway→固定HTTP应答→切回Flash。明确断言真实请求体中的model与后台所选一致、请求关闭Thinking、内部控制字段不外发。

运行时网络隔离，业务库不可访问，仅使用既有合成/内存测试设施；没有患者输入、真实模型调用或病例重跑。相关Ruff及只读ESLint通过，提交前执行编码/凭据检查。未运行全量前端类型检查/单测，因为没有前端或接口类型变更。

代码保存在独立分支，不自动推送、合并、部署或改动已保存模型配置。用户实际切换模型时，走现有后台配置保存流程。
