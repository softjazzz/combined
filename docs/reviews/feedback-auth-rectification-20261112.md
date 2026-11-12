# 演示反馈鉴权与整改任务入口修复

基线：684c040a4e6164181eba5e145b5c37a1eec4d41a。
工作树：D:/MedQC-worktrees/feedback-pg-20261112。
分支：codex/feedback-pg-20261112。

## 修复

- 六个原有 /api/v1/demo/feedbacks 接口（提交、列表、统计、按规则查询、导出、删除）统一使用现有登录令牌和服务端持久角色校验。允许 admin、super_admin、sync_admin；拒绝未登录和其他角色。鉴权在反馈会话创建之前进行。
- 演示反馈包含原文且没有医生/科室所有权字段，故不向普通医生、qc_manager、qc_staff 开放全局记录。正式医生反馈权限、流程、API 和数据模型未修改。
- 演示页反馈请求携带当前令牌，HTTP 失败不会被当成成功导出。反馈请求及响应内容不由新增客户端记录。两个演示入口增加管理员登录守卫。
- 删除移除硬编码 admin888 的假密码校验，保留删除确认，由后端认证授权；不宣称新增密码二次认证。
- /dashboard/qc/rectifications 保留原 URL、名称及角色范围，复用正式 HomeRectificationTodos 页面及 /api/v1/defect-rectifications 合同。没有把两套不兼容载荷仅换 URL，也没有增加旧接口别名。原整改待办、申诉和医生范围保持不变。
- 无迁移，无历史结果或冻结重算，无数据修改脚本。

## 定向验证

后端禁网入口，禁读 dotenv、禁网络、禁非 SQLite 连接、不启动应用 lifespan：

```powershell
python apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_demo_feedback_auth.py tests/unit/test_defect_rectification_api.py
python apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_defect_rectification_service.py
```

47 + 42 = 89 项通过。新增 33 项覆盖六接口的匿名、无效令牌、医生/质控角色拒绝；三类管理员使用实际 JWT 校验完成合成内存 SQLite 全流程。令牌中的伪造 admin 角色不能覆盖账号存储角色。既有正式整改验证覆盖状态流转、医生任务及机构范围。

在 apps/medqc-web 下：

```powershell
node node_modules/vitest/vitest.mjs run src/api/__tests__/demoFeedback.spec.ts src/router/index.spec.ts tests/unit/views/workstation/HomeRectificationTodos.spec.ts
```

40 项通过。覆盖反馈认证请求、错误响应不可下载、令牌不发往外站、旧整改入口复用正式组件、演示页守卫及现有正式整改组件行为。首次运行路由测试因组件已由路由加载导致夹具报错；改为实际导航后比较组件，再运行全三文件通过，未改产品代码迁就测试。

两个演示 Vue 文件通过 SFC 脚本/模板编译检查；后端改动文件 Ruff F、git diff --check 通过。

## 限制与边界

这是工程隔离验证，不是现场浏览器验收；未跑全量、全量类型检查或真实 PG 本轮验证（未改 SQL/模型）。未合并、推送、部署、连接业务库、调用模型、运行质控或重跑27份。未处理独立的业务助手 access 503。未修改现有升级包，本地提交需复审后另行决定交付。


## P2补修：PG验收脚本会话

基于4166e191c，仅修改test_feedback_pg.py：使用固定合成签名配置、精确匹配的合成管理员账号和真实create_access_token，TestClient默认附带Bearer。未覆盖get_current_user或require_roles。monkeypatch在用例退出后恢复。

必要验证：从当前脚本AST抽取原HTTP段，真实路由+合成内存SQLite完成提交、列表、统计、按规则、导出、删除；匿名请求仍在存储前拒绝。两项通过。原文件所有Assert的AST逐一对比基线完全一致，包括迁移、幂等、原SQLite、兼容回滚与新增反馈保护。

本轮没有启动隔离PG或重跑迁移矩阵；验证仅针对改变的认证/HTTP会话，不能称PG端到端重验通过。产品源码、数据模型、医生反馈和历史结果均未修改。新增验证文件在C:/Users/Coldplay/AppData/Local/Temp/MedQC-review-4166e191c/test_p2_client_fix.py，使用同目录run_offline.py禁网入口执行。
