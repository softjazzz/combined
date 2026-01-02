# DRG 分组 API 测试工具

## 📋 目标

通过脚本**直接调用浏览器 Network 中的 `/api/drg-grouping` 接口**，模拟网页里的"执行分组"按钮，验证接口是否能在非浏览器环境返回 DRG 分组结果。

## ✅ 前置条件

* Python ≥ 3.8
* 安装 `requests` 库：`pip install requests`
* 能访问目标站点（无 IP 限制）
* 已在浏览器 Network 中抓到相关信息

## 🔧 配置步骤

### 第一步：打开浏览器开发者工具

1. 访问 DRG 分组网站
2. 按 `F12` 打开开发者工具
3. 切换到 **Network（网络）** 标签
4. 勾选 **Preserve log（保留日志）**

### 第二步：触发分组请求

1. 在网页上填写病例信息
2. 点击 **"执行分组"** 按钮
3. 在 Network 中找到 `drg-grouping` 或类似的请求

### 第三步：复制请求信息

在找到的请求上右键，查看详情：

#### 1. 复制 Request URL
```
示例：https://www.example.com/api/drg-grouping
```
将域名部分填入脚本的 `BASE_URL`

#### 2. 复制 Request Headers
重点关注以下字段（如果存在）：
- `Authorization`
- `Cookie`
- `Referer`
- `Origin`
- `X-CSRF-Token` 等

#### 3. 复制 Request Payload
切换到 **Payload** 标签，复制完整的 JSON 数据

### 第四步：修改脚本

编辑 `drg_grouping_test.py`：

```python
# 1. 修改域名
BASE_URL = "https://你的实际域名"

# 2. 添加必要的请求头
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    
    # 如果有 Cookie，取消注释并填入
    # "Cookie": "session=xxx; token=yyy",
    
    # 如果有 Authorization，取消注释并填入
    # "Authorization": "Bearer xxxxx",
    
    # 如果需要 Referer/Origin
    # "Referer": "https://你的域名/medgroup",
    # "Origin": "https://你的域名",
}

# 3. 替换 PAYLOAD 为 Network 中的真实数据
PAYLOAD = {
    # 粘贴从 Network 复制的完整 JSON
}
```

## 🚀 运行测试

```bash
python drg_grouping_test.py
```

## 📊 结果判断

### ✅ 成功情况

返回类似以下 JSON：
```json
{
  "drgCode": "ES33",
  "drgName": "呼吸系统感染/炎症，伴并发症或合并症",
  "rw": 0.5534,
  "mdcCheck": "pass",
  "adrgCheck": "pass",
  "drgCheck": "pass"
}
```

**结论**：接口可被程序化调用 ✅

### ❌ 失败情况及解决方案

| HTTP 状态码 | 可能原因 | 解决方案 |
|------------|---------|---------|
| 401 Unauthorized | 缺少认证信息 | 检查并添加 `Authorization` 或 `Cookie` |
| 403 Forbidden | 存在风控/IP限制 | 检查 `Referer`、`Origin`，或可能需要浏览器指纹 |
| 400 Bad Request | Payload 结构不匹配 | 仔细对比 Network 中的 JSON 结构 |
| 非 JSON 响应 | 可能有签名验证 | 检查是否有时间戳、签名等额外参数 |

## 🔍 调试技巧

### 1. 对比完整请求

在浏览器中右键请求 → **Copy as cURL**，与脚本对比差异

### 2. 检查响应头

```python
print("Response Headers:", dict(resp.headers))
```

### 3. 保存原始响应

```python
with open("response.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
```

### 4. 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 常见问题

### Q: 提示 "No module named 'requests'"
```bash
pip install requests
```

### Q: 返回 HTML 登录页面
说明需要登录态，检查 Cookie 是否正确复制

### Q: 返回空 JSON `{}`
可能缺少必要的请求头或参数，仔细对比 Network

### Q: 证书错误
临时解决（仅测试用）：
```python
resp = requests.post(url, headers=HEADERS, json=PAYLOAD, verify=False)
```

## 🎯 下一步

如果测试成功，可以：

1. **标准化 API Schema** - 整理成统一的输入输出格式
2. **构建代理服务** - 使用 FastAPI/Express 封装
3. **评估商业可行性** - 检查使用条款和限制
4. **实现错误处理** - 添加重试、降级等机制

## 📞 需要帮助？

将脚本执行结果（包括完整的输出和错误信息）反馈，可以进一步诊断问题。
