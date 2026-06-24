# SQLBot 问数集成说明

## 定位

SQLBot 作为第三方子项目放在 `third_party/sqlbot/`，默认独立部署。本项目第一阶段只提供“智能助手”里的问数入口和 iframe 嵌入配置，不替换现有质控、编码、DRG/DIP 受控 Agent。

## 部署边界

- SQLBot 服务独立启动和维护。
- SQLBot 数据源必须配置为只读视图或分析库。
- 禁止直接连接生产病历全文表、正式写库账号或可修改业务数据的数据源。
- 本项目后端只返回嵌入配置，不返回 SQLBot 密钥。

## 安全边界

问数能力不得暴露或转发以下字段：

- `medical_text`
- `documents`
- `bundle`
- `record_content`
- `internal_data`
- `prompt`
- `raw_response`
- `embedding`
- `vector`

SQLBot 的自由问数能力不进入 `/api/v1/qc-agent/chat`，也不写正式病案首页、医保结算清单、质控结果表或正式 DRG/DIP 结果。

## 配置项

```env
SQLBOT_ENABLED=false
SQLBOT_BASE_URL=
SQLBOT_EMBED_URL=
SQLBOT_APP_ID=
SQLBOT_TIMEOUT_SECONDS=30
```

`/api/v1/sqlbot/config` 返回字段：

- `enabled`: 是否可用
- `base_url`: SQLBot 服务地址，不含密钥
- `embed_url`: iframe 嵌入地址
- `app_id`: 可选展示标识
- `display_mode`: `iframe` 或 `disabled`
- `message`: 面向前端的配置状态说明

## 前端行为

智能助手中新增“问数”能力入口。未配置时显示“SQLBot 未启用/待接入”的可读提示；配置完成后打开独立嵌入面板。第一版不把 SQLBot 的 Text-to-SQL 结果转换为本项目结构化结果卡。
