# 手术文书展示独立复审与交付

固定候选 ca70ae428，对比 d65d8148d。两名独立审查者使用固定提交的独立工作树；整合到 PR #55 的 0e2a5670e 上得到 99cc7f0d8，应用代码未额外修改。

## Standards

PASS：未发现阻断性规范或可维护性问题。正文组装、元数据传递和前端展示职责分离；源状态原样显示，提交时间未冒充记录时间。字段展示顺序与有效内容白名单用途不同。

## Spec

未确认 P1/P2 或范围越界。surgery_process 完整渲染，内部冒号和换行保留；两套手术时间分别保留；提交、修改时间不冒充记录时间；原始状态及文书身份直接传递，无新增签署判定或同日合并；无有效内容时不制造模板正文。未修改同步或质控判定。

## 必要隔离验证

工作目录 apps/medqc-web/backend：

```powershell
python -B scripts/run_pr8_offline_tests.py tests/unit/test_surgery_record_current_display.py tests/unit/test_document_assembly_surgery_record.py tests/unit/test_bundle_emr_view.py tests/unit/test_emr_independent_cdm_browse.py -p no:cacheprovider
```

整合后 51 项通过。随后仅补测试：完整长正文的来源表及字段、只有修改时间不成为记录时间；重新运行 test_surgery_record_current_display.py，6 项通过（其余三个文件未重复运行）。首次新增断言误要求顶部显示回退时间，实际合同是修改时间独立展示，已更正测试，产品代码未改。

工作目录 apps/medqc-web：

```powershell
node node_modules/vitest/vitest.mjs run tests/unit/components/EMRViewer.spec.ts --config vitest.config.ts --maxWorkers=1 --minWorkers=1
```

原 7 项通过；补充回退时间标签对照后 8 项通过。正文 DOM textContent 与完整输入相等。此验证仅证明字段来源和全文展示，不声称已验证质控引文高亮定位。

## 依赖与限制

本分支堆叠在 PR #55 上，Draft PR 暂以其分支 codex/linux-patch-integration-20261111 为目标，仅展示手术改动。#55 合入后再调整为 codex/business-agent-integration 并核对差异，不自动合并。

未连接数据库、Caché 或模型；未执行质控、27份病例、全量测试或现场浏览器验收。未部署、制包、变更旧冻结或历史结果。上游实际发布、真实时间/状态语义、49列全部供给不属于本次通过范围。此修复不能让尚未发布到 CDM 的手术记录凭空出现。
