# 原始 LX0609 病程族已发布事实读取边界

## 身份、问题与范围

本次工作树起点为 `9dc1edc02`。先按 `docs/0602/luxian_0609_formal_rule_catalog.csv` 确认原始 007、008、009、016、017、018，分别映射内部规则 ID `LX0609-02-01-03`、`02-01-04`、`02-01-05`、`12-01-01`、`12-01-02`、`01-01-02`。六条均在正式目录 001–049 范围内，未改变其允许状态、判据或原因码。

Finalizer 旧读取路径对除 007 外的五条仍调用执行器内部白名单投影。固定反例：016 已发布 `copy_similarity=0.123456` 被读取成 `0.1235`；008 已发布正常形态附加 `unexpected_field` 后被静默删键并成功读取。其共同原因是用首次发布的内部事实投影代替已发布 JSON 合同校验。

本次只在现有 `course_quality_result_mapping.py` 内增加一个族入口和四个公开形态校验器，Finalizer 对六条使用同一个入口。007 复用已验收的独立公开校验器；018 无独立 facts 时继续接受 `None`，空对象继续接受 `{}`。首次内部投影、状态判定、执行器、Prompt、模型、聚合和事实证据定位未改。合法已发布 facts 逐值返回；未知键、缺键、错误 JSON 类型、非有限数、超出发布精度的相似度及嵌套事件/配对损坏受控拒绝，Canonical Store 读取不再静默修正。

新增生产代码为病程族模块 167 行、Finalizer 净增 5 行，均未达到单文件新增 200 行门槛。职责留在已有病程族事实合同模块，避免拆出转发壳或重复事实所有者；公共 Finalizer 没有逐规则分派。

## 冻结与验证

- 起点已有 `test_luxian_0609_course_quality_freeze.py` 固定五条原始病程族的 native → Binding → Aggregator 输入、状态、原因码、公开事实、证据坐标和调用/Token；017 使用固定模型响应，其余该组零调用。改后此冻结组 9 项通过。008/009 的该组样本是 `not_applicable`，不能据此推断其合规/不合规临床准确率。018 无独立 facts，通过现有原生执行测试与本次 `None`/`{}` 合同测试保护。
- 新增公开形态测试覆盖 008 超间隔及达标、009 时间不可得/关联失败/观察窗口未到/事件及时与超时/每日覆盖与缺失、016 完全相同与不同、017 阈值超出/阈值内/语义审核通过/模板壳通过、018 空对象。每一形态先用旧首次投影生成公开 facts，再断言新读取逐值相等并拒绝未知键；损坏类型、NaN/Infinity、四位小数精度和嵌套事件另测。此校验不调用 `_safe_*` 或重做业务推断。
- SQLite Canonical Store 完整写读 008 已发布事实保持逐值相等；污染 Envelope 加额外键后 `load_selected` 抛出既有解释合同 `ValueError`。这只证明隔离 SQLite 读取边界，未做 PostgreSQL 或客户浏览器验收。
- 聚焦及相邻组命令（`backend` 目录，配置伪 PG DSN 与隔离 JWT）：`py -3.10 -m pytest --confcutdir=tests/unit -q tests/unit/test_luxian_0609_course_family_public_boundary.py tests/unit/test_luxian_0609_original_007_public_boundary.py tests/unit/test_luxian_0609_course_quality_freeze.py tests/unit/test_luxian_0609_native_course_quality_execution.py tests/unit/test_luxian_0609_canonical_result_finalizer.py --tb=line`：350 passed。改动文件 `ruff check` 和 `git diff --check` 退出 0。
- 暂存区四个精确路径执行 `npm run check:encoding` 通过。隔离工作树未安装 `node_modules`，`npm run lint` 退出 1（`eslint` 未找到）；未运行同样依赖前端工具链的 `type-check` 和 `test:unit`。本次未修改前端。

## 未验收项

007 的 72 小时加 1 秒既有发布失败继续由 `2026-09-24-original-engine-007-published-facts.md` 单独记录，本次没有修改临界发布判据。固定合成来源与固定响应证明读取合同和现有链路回归，不是 008/009/016/017/018 的真实病例临床签收；客户 PostgreSQL、前端展示、真实模型输出及完整业务保护集仍需主协调另行验收。读取与导出本次没有增加 LLM 调用。
