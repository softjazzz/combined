# Mongo→PG→首页/医保质控 全链路联调 SOP（双轨）

## 1. 目标

用同一病例完成以下闭环并产出可复核证据：

1. MongoDB 抽取并同步到 PG
2. 系统首页（官方数据）可读取
3. 首页形式质控可执行
4. 医保结算清单质控可执行
5. 脚本报告与前端页面展示一致

---

## 2. 自动化轨（脚本验收）

### 2.1 运行命令

在 `apps/medqc-web/backend` 目录执行：

```bash
python -m scripts.run_case_e2e \
  --base-url http://localhost:8001 \
  --patient-id <PATIENT_ID> \
  --visit-id <VISIT_ID> \
  --tier all \
  --with-generate-qc \
  --api-email admin@medqc.com \
  --api-password <PASSWORD>
```

也可用 token：

```bash
python -m scripts.run_case_e2e \
  --patient-id <PATIENT_ID> \
  --visit-id <VISIT_ID> \
  --api-token <BEARER_TOKEN>
```

### 2.2 报告位置

- 输出目录：`apps/medqc-web/backend/reports/e2e/`
- 文件名：`case_e2e_<patient_id>_<visit_id>_<timestamp>.json`

### 2.3 核心报告字段

- `case_meta`: 病例标识、运行耗时、环境信息
- `sync_result`: 连通性、预检、触发结果、最近一次同步运行记录
- `input_records`: Mongo 与 PG 的记录存在性和条数
- `frontpage_mapping_checks[]`: 字段级比对（`source_value/pg_value/frontpage_render_value`）
- `mapping_summary`: 命中率、关键字段是否全部通过、差异字段
- `frontpage_qc_summary`: 首页形式质控汇总
- `settlement_qc_summary`: 医保结算质控汇总
- `generated_settlement_qc_summary`: 生成草稿质控汇总（可选）
- `final_status`: 总体结论、错误和告警

---

## 3. 前端轨（演示验收）

### 3.1 固定演示路径

1. 打开病例详情页（同 `patient_id + visit_id`）
2. 不点击 AI 生成，直接进入“病案首页”并切到“系统首页”
3. 核对“系统首页”字段是否有值（或空表模板）
4. 切“首页预览/打印”，对比 LLM 草稿差异
5. 打开分析面板，执行：
   - 首页质控
   - 编码/医保结算质控
6. 打开证据详情，核对问题条数与级别

### 3.2 与脚本对照的验收点

1. `mapping_summary.mismatch_fields` 中的字段，前端应能看到对应差异或缺失
2. `frontpage_qc_summary.failed` 与前端首页质控失败项数量一致（允许排序差异）
3. `settlement_qc_summary.summary.failed` 与前端医保质控失败数一致
4. `final_status.errors` 不应出现同步触发失败/鉴权失败等硬错误

---

## 4. 判定标准

### 通过（PASS）

1. 同步链路成功（连接、预检、触发均成功）
2. `mapping_summary.critical_all_passed = true`
3. 首页质控和医保质控接口均可执行并返回结构化结果
4. 前端展示与脚本报告对得上同一问题集合

### 告警（WARN）

1. 链路可跑通，但存在字段差异或部分数据缺失
2. 接口返回正常但存在明显一致性偏差

### 失败（FAIL）

1. 同步链路关键步骤失败（连接/预检/触发）
2. 无法获取病例核心数据（官方首页、结算清单均不可用）
3. 报告与前端结果明显不一致且无法解释
