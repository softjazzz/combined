# 配置示例文件
# 这个文件展示了如何从浏览器 Network 中提取信息并填入脚本

## 示例 1：基础配置（无认证）

### Network 中看到的请求：
```
Request URL: https://drg.example.com/api/drg-grouping
Request Method: POST
```

### 对应的脚本配置：
```python
BASE_URL = "https://drg.example.com"
API_PATH = "/api/drg-grouping"
```

---

## 示例 2：带 Cookie 认证

### Network Headers 中看到：
```
Cookie: sessionId=abc123; userId=456; token=xyz789
Referer: https://drg.example.com/medgroup
Origin: https://drg.example.com
```

### 对应的脚本配置：
```python
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    "Cookie": "sessionId=abc123; userId=456; token=xyz789",
    "Referer": "https://drg.example.com/medgroup",
    "Origin": "https://drg.example.com",
}
```

---

## 示例 3：带 Bearer Token

### Network Headers 中看到：
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 对应的脚本配置：
```python
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
}
```

---

## 示例 4：完整 Payload 示例

### Network Payload 中看到：
```json
{
  "type": "DRG",
  "city": "北京市",
  "gender": "男",
  "age": 45,
  "birthWeight": 0,
  "los": 7,
  "icu": "否",
  "diagnosisList": [
    {
      "code": "I21.001",
      "name": "急性ST段抬高型心肌梗死",
      "main": true
    },
    {
      "code": "I10.x00",
      "name": "高血压",
      "main": false
    }
  ],
  "procedureList": [
    {
      "code": "36.06001",
      "name": "冠状动脉旁路移植术"
    }
  ]
}
```

### 对应的脚本配置：
```python
PAYLOAD = {
    "type": "DRG",
    "city": "北京市",
    "gender": "男",
    "age": 45,
    "birthWeight": 0,
    "los": 7,
    "icu": "否",
    "diagnosisList": [
        {
            "code": "I21.001",
            "name": "急性ST段抬高型心肌梗死",
            "main": True  # 注意：Python 用 True，不是 true
        },
        {
            "code": "I10.x00",
            "name": "高血压",
            "main": False
        }
    ],
    "procedureList": [
        {
            "code": "36.06001",
            "name": "冠状动脉旁路移植术"
        }
    ]
}
```

---

## 快速提取技巧

### Chrome DevTools
1. 找到请求后右键
2. 选择 **Copy** → **Copy as fetch**
3. 会得到类似这样的代码：
```javascript
fetch("https://drg.example.com/api/drg-grouping", {
  "headers": {
    "accept": "application/json",
    "cookie": "session=xxx",
    // ...
  },
  "body": "{\"type\":\"DRG\",\"city\":\"北京市\",...}",
  "method": "POST"
});
```
4. 将其转换为 Python 格式即可

### Firefox DevTools
1. 右键请求 → **Copy** → **Copy as cURL**
2. 使用在线工具转换 cURL 到 Python（如 curlconverter.com）

---

## 注意事项

⚠️ **JSON 格式差异**
- JavaScript: `true`, `false`, `null`
- Python: `True`, `False`, `None`

⚠️ **Cookie 时效性**
- Cookie 可能会过期
- 如果返回 401，需要重新登录并获取新的 Cookie

⚠️ **动态参数**
- 某些接口可能包含时间戳、随机数、签名等
- 如果发现这些参数，需要在脚本中动态生成
