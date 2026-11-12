# 已部署补丁与推理配置的Linux交付整合

基线：最新远端business-agent-integration固定8c6a44bb1。独立分支codex/linux-patch-integration-20261111，不合并、不部署。

用户确认现场已安装后端6cd06ff77即时装配，以及前端697ab73ca抽屉与排版补丁；早期eb2fbb4ca亦已安装。
顺序承接50e0127d4、eb2fbb4ca、15f9756c9、6cd06ff77、2b5c93003、c53ec65a2、697ab73ca。
补丁工具及原说明仅作为历史交付证据，不在升级时重新执行。
不纳入未确认部署的ca70ae428手术文书展示候选；不扩展质控规则或同步服务。

整合后src/views、src/styles和backend/app/routers/emr_render.py与697ab73ca无差异；推理端点服务、权限、密钥保护、前端抽屉及冻结身份代码与8c6a44bb1无差异。保留现有部署配置回退和历史结果读取。

必要隔离验证（整合工作树）：

```text
cd apps/medqc-web/backend
python -B scripts/run_pr8_offline_tests.py -p tests.fixtures.llm_admin_offline tests/unit/test_emr_independent_cdm_browse.py tests/unit/test_current_document_view.py tests/unit/test_llm_endpoint_settings.py -p no:cacheprovider
```

45项通过。取材读取替身、HTTP夹具不启动后台作业，端点密钥/冻结使用临时合成目录；未连接业务库、模型或运行质控任务。

```text
cd apps/medqc-web
node node_modules/vitest/vitest.mjs run tests/unit/components/LLMEndpointSettings.spec.ts tests/unit/components/LLMApiConfigStrata.spec.ts tests/unit/views/workstation-v4/useFrontpageDraft.source.spec.ts tests/unit/views/workstation-v4/CDMDataView.source.spec.ts tests/unit/views/workstation-v4/BatchTablePanel.spec.ts tests/unit/views/workstation-v4/QcRecordResultListView.spec.ts tests/unit/views/workstation-v4/components/qc/QcRecordResultTable.spec.ts tests/unit/views/workstation-v4/RecordDetailWorkspace.panel.spec.ts --config vitest.config.ts
```

8文件92项通过，git diff --check通过。node_modules复用既有目录联接，无依赖安装。

制包前固定本地Commit，前后端统一版本；构建与包验证另附SHA256绑定报告，不用源码测试冒充Linux启动通过。
新包以现场e1后端+6cd即时装配补丁+697前端为预期基线，须核对实际文件哈希；未知补丁停止，不删除原receipt。
升级不迁移数据库（保留064）、不覆盖配置/旧冻结/1026/历史结果，原release连同补丁备份保留供回滚。新端点密钥与设置必须成套保存在release外部；旧版本回滚后仍使用原部署配置。
