# 东华普通病例详情空白：目录与正文只读接入

基线：15f9756c9，独立分支 codex/cdm-record-view-20261110。

## 已确认的代码问题

工作台点击查看调用 `/api/v1/emr/{visit}/documents?view=summary`，随后调用同族 render。
这与现场此前核对的 `/api/medical-records/documents/{visit}` 不是同一条读取链。
原目录只查持久 Bundle 的 source_documents 索引；没有 Bundle 就返回 HTTP 200 和空目录。
原 render 同样依赖 Bundle。AI 草稿修复不能解决这个问题，助手 access 503 也不是这条调用链的前置条件。

现场本次截图未提供 EMR 响应，因此尚不能宣称已对截图对应病例完成现场根因复核或验收。
两张截图的就诊号不同，不据此认定串病例；本文和测试不保存患者信息。

## 修改

- 普通独立 CDM 浏览在目录、完整文书和正文渲染中复用 load_current_documents 的只读即时装配，不创建/刷新持久 Bundle。
- 已绑定的任务材料快照仍优先并校验身份；历史缺快照仍由既有请求门禁阻断。1026/本地专用材料路径保持原样。
- 三坐标缺失返回 422；临床读取异常返回脱敏 503，不以空目录掩盖、不回退旧材料。
- 当前文书的指定 ID 不存在时不借另一份文书显示。
- 不改前端、业务数据库、来源配置、历史结果、旧冻结或调度。

## 必要验证

新增路由反例在修复前 6 失败、2 对照通过，证明无 Bundle 空目录/空正文及错误空响应。
补充指定文书不存在保护，以及真实装配器→摘要→正式 render 的合成链验证。
该链仅替换临床行读取边界，不依赖持久 Bundle；断言持久 Bundle 的读取/刷新/写入未被调用。

禁网入口执行文件：

```text
python scripts/run_pr8_offline_tests.py tests/unit/test_emr_independent_cdm_browse.py tests/unit/test_emr_render_performance_contract.py tests/unit/test_current_document_view.py tests/unit/test_case_material_snapshot.py
```

最终集合中68项通过；新增真实装配用例因夹具未提供模拟CDM engine初次失败，补齐读取边界替身后单独复跑1项通过。无产品代码通过放宽断言处理。
Ruff F、git diff --check 通过。

## 待现场验证与限制

这是后端修复，现有 eb2fbb4ca 前端补丁不包含本改动。未打包、推送或部署。
没有连接现场或业务库、调用模型、启动任务或重跑27份。
当前只读装配对每次查看重新读取材料，仅合并同时进行的请求；尚未测服务器耗时及并发。
目录响应仍裁去正文，但当前装配需要读取完整材料；并非新的数据库级摘要查询优化。
后续交付须在同一选中病例上核对 EMR summary/full/render 的身份、数量和可读正文；单独验证 medical-records 接口200不足以验收。
