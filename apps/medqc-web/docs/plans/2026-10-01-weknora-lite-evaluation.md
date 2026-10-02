# WeKnora Lite 测试阶段适用性评估

日期：2026-10-01。结论：Lite 值得作为本项目单账号、小规模规范库的候选；源码接口初步兼容，尚未完成编译、启动或真实检索验收，不能称已经安装可用。

## 已完成的实际动作

- 通过官方 GitHub Release API 查询，最新发布为 v0.8.2（2026-09-24），assets 为空，没有可直接下载的 Lite 或 Windows 安装包。
- 已下载官方 v0.8.2 源码到 `D:/LLM/WeKnora-Lite-evaluation/WeKnora-v0.8.2-source.tar.gz`，完整解压4355个普通文件至相邻 `WeKnora-0.8.2/`。Windows tar 对两个中文文件名报错后，改用校验目标路径边界的 Python 解压，特殊文件条目为0。
- 源码包本机 SHA256：`0D30C5415A43674D4D134293DD27ECB1A3903FC70E19F22E3133AB8E9C193239`。这是下载后计算的留档值，不冒充官方签名或官方校验文件。
- 保留 `D:/LLM/WeKnora` 原版本；未改数据库、共享队列、主服务或 MedQC 凭据，未新增模型调用。

## 对当前项目的适用性

用户明确当前只有 admin 测试账号，因此不再将缺少实际医生/科室管理者账号作为测试阶段阻塞项；仍须保留病例/科室范围校验、越界拒绝和角色单测，不能据管理员联调宣称生产医院权限验收完成。

Lite 配置使用 SQLite、FTS5/sqlite-vec、本地文件及内存流管理，适合少量规范资料验证。数据库和 Redis 不必独立部署；模型/Embedding 服务仍需按实际检索配置，不能把“基础设施零外部依赖”解释为无需任何模型服务。

v0.8.2 的 `docs/LITE.md` 明确不提供共享空间，适合当前单账号验证；多人协作、跨成员知识库共享不在本次候选承诺内。

## 与已安装 DSH 插件的接口比对

对照 MedQC 固定的 `@wxg-prc-cpg/dsh-weknora@0.1.0` 客户端与 v0.8.2 路由/handler 源码：

| 现有插件需求                       | v0.8.2 源码证据                                                                                       | 结论                           |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------ |
| `POST /api/v1/knowledge-search`    | `routes_chat.go`、`handler/session/qa.go`；接受query、knowledge_base_ids、knowledge_ids，返回data列表 | 请求及响应外层匹配             |
| `GET /api/v1/knowledge/search`     | `routes_knowledge.go`、`handler/knowledge.go`；接受keyword与limit                                     | 名称搜索入口匹配               |
| `GET /api/v1/knowledge/:id`        | `routes_knowledge.go`                                                                                 | 文档详情入口保留               |
| `GET /api/v1/chunks/:knowledge_id` | `routes_knowledge.go`、`handler/chunk.go`；page/page_size，返回data/total/page/page_size              | 原文分页外层匹配               |
| `X-API-Key`及retrieve能力          | 路由API Key guard及能力测试中声明检索/详情/分块读取能力                                               | 可沿用限定知识库的只读密钥设计 |

以上为静态检查，未执行 Lite 服务请求，不能据此宣称权限、命中排序、引用正文和真实文档已全部兼容。MedQC 仍只启用搜索与原文读取，不启用 WeKnora 委托问答。

## 文档格式限制

v0.8.2 默认 `make build-lite` 仅使用 `sqlite_fts5` build tag，未链接可选 anydoc 引擎。内置 SimpleFormatReader 对 Markdown/TXT/CSV/JSON有直接处理路径；PDF/DOCX不在该简单格式列表，默认会转交文档解析服务。不能承诺仅靠默认 Lite 构建就完整解析扫描版医疗规范PDF。

首批建议使用保留标题、条款号和出处的少量 Markdown/TXT 规范，先验收检索→引用→分页原文。复杂PDF解析应另验，不静默上传到云解析服务。

## Windows 与本机启动检查

- `go.mod` 要求 Go 1.26.0，构建开启CGO，需要C编译器；本机PATH未发现Go、GCC、Clang或Make，常见Go/MSYS2路径也未发现。
- 官方 `release-lite.yml` 的Web CLI矩阵只有Linux/macOS；桌面应用矩阵含Windows，但tag自动触发被注释，且当前Release没有产物。Windows代码存在并不等于本机或官方发布包已经运行通过。
- 本机WSL列出Ubuntu，但实际执行失败：其ext4.vhdx缺失，错误为 `MountVhd/HCS/ERROR_FILE_NOT_FOUND`。没有注销、重装或修改该发行版。
- 因没有发行二进制和可用编译环境，本次没有启动Lite，未创建账号/知识库或调用Embedding/聊天模型。

## 决策与下一步

优先保留Lite候选，进入独立源码构建验证；先准备目录内的Go 1.26与兼容C工具链，验证Windows构建能否成功，不将修复损坏WSL作为默认前置步骤。若Windows依赖不兼容，再选可用Linux环境构建；当前证据不足以承诺Windows“一键安装”。

构建成功后，使用独立SQLite数据目录和本机独立端口做health、登录及只读API检查，再用限定知识库和少量规范验收真实检索/引用/原文。初始化新Lite测试库属于后续实际部署工作；本次评估没有自动创建或修改业务账号、数据库及密钥，也没有突破既有真实聊天10回合预算。

## 来源

- [官方v0.8.2发布页](https://github.com/Tencent/WeKnora/releases/tag/v0.8.2)
- [官方Release API](https://api.github.com/repos/Tencent/WeKnora/releases/latest)
- [官方部署说明](https://weknora.weixin.qq.com/docs/01-getting-started/02-installation)
- [v0.8.2 Lite构建工作流](https://github.com/Tencent/WeKnora/blob/v0.8.2/.github/workflows/release-lite.yml)
- [v0.8.2 Lite说明](https://github.com/Tencent/WeKnora/blob/v0.8.2/docs/LITE.md)

此前将新版Lite描述为可直接下载运行的选项不够准确：当前公开提供的是源码与构建流程，而非可用安装包。本记录更正该表述。
