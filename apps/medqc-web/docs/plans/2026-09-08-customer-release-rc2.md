# 客户正式部署包 RC2 Implementation Plan

**Goal:** 收口当前已授权工作台代码，在干净工作树生成可追溯客户部署ZIP，并完成包内验收。

**Architecture:** 保留现有Vue/FastAPI部署合同；只修复打包脚本未检查Vite退出码的问题。
现有开发工作区和临时病例资料保留，构建在独立工作树执行；不使用AllowDirty。

**Tech Stack:** Vue 3、TypeScript、Vite、Python/FastAPI、PowerShell、PostgreSQL。

## 范围与证据

- 基线adb82e0e9，最终工作区实际变更集中于首页、单病例结果、任务状态条、字体及CSS构建。
- 索引内有与工作区相互抵消的旧编辑；按HEAD到工作区的最终内容审查，定向提交。
- index.prebuilt.css是开发生成产物，生产Vite使用index.css，本轮不提交生成文件。
- package-customer-release.ps1未检查Vite退出码，失败时可能复制旧dist，先建立失败回归再修复。
- 不修改临床规则，不发布未验收完整模型录制回放能力，不迁移客户数据库。

## 执行步骤

1. 独立只读审查UI最终差分，主代理亲审业务统计和数据投影；运行聚焦及全量前端检查。
2. 白名单scripts/package-customer-release.ps1及对应后端脚本合同测试：
   加入Vite非零退出码检查、dist/index.html存在性检查。失败回归先红后绿。
3. 只提交明确源码、测试和发布文档；保留临时资料、原始病例、构建输出。
4. 创建docs/releases/20260908-customer-rc2/change-inventory.json，说明纳入与排除项。
5. 从最终提交创建.release-packages/下独立工作树，连接已有Node依赖而不改变依赖版本。
6. 执行正式源码校验和客户模式构建，保留脚本默认三个月试用授权；签发私钥不进入包。
7. 校验ZIP内版本、必需模块、排除项、字体与公共API地址，解压至独立验收目录。
8. 包内Python导入/健康接口、静态页面、登录及结果/诊断入口验收；本机数据库只读预检。
   任何环境或功能限制如实记录，不把进程启动等同完整客户部署验收。

## 验收与风险

源码门禁通过；构建非零退出必须阻断；ZIP标识与最终提交一致；包内不包含开发密钥、
本地数据库、病例临时文件或字体；页面和质控回读可用。保留普通浏览器实际下载和
干净客户机依赖安装的验证边界。失败只修当前发布阻断，不扩大平台或规则范围。

## 干净构建暴露的授权签发阻断

- 9ce41076e 前端构建成功，签发预激活状态时因缺少 JWT_SECRET 失败，未产出 ZIP。
- 根因：ProductActivationService 已接收完整离线参数仍无条件读取服务器 Settings。
- 最小修改：仅在 required/state_path 需要默认值时读取 Settings，显式离线参数继续使用原验签和落盘流程。
- 范围：product_activation.py 及对应测试；验收显式参数不读取 Settings、默认运行时参数继续生效、现有授权测试通过。

## 客户 API 地址发布阻断

- 包检查发现 5 个 JS 分块内含旧公网 IP，6 处源码分支在内网或 127.0.0.1 访问时仍选旧公网后端。
- 根因：5 个旧页面/服务绕过已有 resolveApiBaseUrl；源码与产物门禁仅检查 api.medqc.com。
- 最小修改：5 个入口复用现有 helper，保持请求合同；两层门禁同时识别已知旧公网 IP，不新增 API 配置层。
- 验收：同源及显式 API 配置下真实服务 fetch 地址正确；旧公网源码/产物被门禁拒绝；最终 ZIP 无旧公网 API 地址。
