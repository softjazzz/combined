# ICD 编码提取 API 接入说明

## 1. 服务概述

外部 ICD 编码提取服务，基于 LLM 从病历文本中自动识别诊断和手术操作，并推荐对应的 ICD 编码。

| 项目 | 说明 |
|------|------|
| **服务地址** | `http://122.51.111.253:8002` |
| **协议** | HTTP/JSON |
| **认证** | 无需认证 |
| **处理模式** | 异步 (Job Queue) |

---

## 2. 对接流程

```
┌─────────────┐      POST /extract       ┌─────────────┐
│  客户端     │  ──────────────────────▶ │  编码服务   │
│             │      返回 job_id         │             │
│             │  ◀────────────────────── │             │
│             │                          │             │
│             │      GET /jobs/{id}      │             │
│             │  ──────────────────────▶ │  轮询状态   │
│             │      返回结果            │             │
│             │  ◀────────────────────── │             │
└─────────────┘                          └─────────────┘
```

---

## 3. API 接口

### 3.1 提交编码任务

**请求**
```http
POST /api/v1/coding/extract
Content-Type: application/json
```

**参数**
```json
{
  "request_id": "req_10086",           // 请求唯一标识
  "document_type": "admission_note",   // 文书类型
  "text_content": "病历全文...",        // 病历文本
  "patient_context": {                 // 患者上下文
    "gender": "M",                     // M-男 F-女
    "age": 58                          // 年龄
  },
  "coding_mode": "default"             // 编码模式
}
```

**document_type 可选值**
| 值 | 说明 |
|----|------|
| `admission_note` | 入院记录 |
| `progress_note` | 病程记录 |
| `discharge_note` | 出院记录 |
| `operation_note` | 手术记录 |

**响应** (HTTP 202)
```json
{
  "message": "accepted",
  "data": {
    "job_id": "job_xxx",
    "request_id": "req_10086"
  }
}
```

---

### 3.2 查询编码结果

**请求**
```http
GET /api/v1/coding/jobs/{job_id}
```

**响应状态码**
| 状态码 | 含义 | 处理方式 |
|--------|------|----------|
| 200 | 编码完成，可直接使用 | 读取 `data.coding_data` |
| 422 | 编码完成，需人工确认 | 展示结果 + 显示警告 |
| 500 | 服务异常 | 重试或降级 |

**成功响应结构**
```json
{
  "message": "success",
  "data": {
    "sys_meta": {
      "job_id": "job_xxx",
      "model_version": "qwen3-next-80b-a3b-instruct",
      "processing_time_ms": 4175
    },
    "patient_context": {
      "gender": "M",
      "age": 58
    },
    "coding_data": {
      "principal_diagnosis": {
        "code": "J18.900",
        "name": "肺炎，未特指",
        "confidence": 0.95,
        "evidence_spans": [
          {"start": 560, "end": 567, "text": "肺炎（右下肺）"}
        ]
      },
      "secondary_diagnoses": [
        {
          "code": "J96.900",
          "name": "呼吸衰竭",
          "confidence": 0.88,
          "evidence_spans": [
            {"start": 571, "end": 576, "text": "呼吸衰竭？"}
          ]
        }
      ],
      "principal_procedures": [],
      "secondary_procedures": []
    },
    "warnings": [
      {
        "field": "principal_diagnosis",
        "reason": "low_confidence",
        "message": "初步诊断为疑似，建议结合检查确认",
        "candidates": [
          {"name": "肺炎", "confidence": 0.95},
          {"name": "细菌性肺炎", "confidence": 0.85}
        ]
      }
    ]
  }
}
```

---

## 4. 关键字段说明

### coding_data 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `principal_diagnosis` | object | 主要诊断 (ICD-10) |
| `secondary_diagnoses` | array | 次要诊断列表 |
| `principal_procedures` | array | 主要手术操作 (ICD-9-CM-3) |
| `secondary_procedures` | array | 次要手术操作 |

### 诊断/手术对象结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | ICD 编码 |
| `name` | string | 诊断/手术名称 |
| `confidence` | number | 置信度 (0-1) |
| `evidence_spans` | array | 证据位置 |

### evidence_spans 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `start` | int | 起始字符偏移量 |
| `end` | int | 结束字符偏移量 |
| `text` | string | 匹配的原文片段 |

---

## 5. 轮询策略

```python
import time
import requests

def poll_coding_result(job_id, max_retries=15, interval=2):
    """轮询编码结果"""
    url = f"http://122.51.111.253:8002/api/v1/coding/jobs/{job_id}"
    
    for i in range(max_retries):
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data", {}).get("coding_data"):
                return {"success": True, "needs_review": False, "data": data["data"]}
                
        elif resp.status_code == 422:
            # 422 = 成功但需人工确认
            return {"success": True, "needs_review": True, "data": resp.json()["data"]}
            
        elif resp.status_code == 500:
            return {"success": False, "error": "服务异常"}
        
        time.sleep(interval)
    
    return {"success": False, "error": "轮询超时"}
```

**建议参数**
- 轮询间隔: 2 秒
- 最大重试: 15 次
- 总超时: 30 秒

---

## 6. 前端证据高亮实现

```typescript
// 根据 evidence_spans 高亮原文
function highlightEvidence(text: string, spans: Array<{start: number, end: number}>) {
  // 按 start 降序排序，从后往前替换避免偏移
  const sorted = [...spans].sort((a, b) => b.start - a.start)
  
  let result = text
  for (const span of sorted) {
    const before = result.slice(0, span.start)
    const match = result.slice(span.start, span.end)
    const after = result.slice(span.end)
    result = `${before}<mark class="evidence-highlight">${match}</mark>${after}`
  }
  
  return result
}
```

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|----------|
| 网络超时 | 重试 3 次，间隔 exponential backoff |
| 422 返回 | 正常展示结果，同时显示 warnings |
| 500 错误 | 降级到 LLM 本地推理 |
| 轮询超时 | 提示用户稍后重试 |

---

## 8. 集成示例

### 后端代理服务

```python
# backend/app/services/external_coding_service.py

class ExternalCodingService:
    BASE_URL = "http://122.51.111.253:8002"
    
    async def extract_coding(self, medical_text: str, patient: dict) -> dict:
        """提取 ICD 编码"""
        # 1. 提交任务
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                f"{self.BASE_URL}/api/v1/coding/extract",
                json={
                    "request_id": f"req_{uuid.uuid4().hex[:8]}",
                    "document_type": "admission_note",
                    "text_content": medical_text,
                    "patient_context": patient,
                    "coding_mode": "default"
                },
                timeout=30
            )
            job_id = resp.json()["data"]["job_id"]
        
        # 2. 轮询结果
        for _ in range(15):
            await asyncio.sleep(2)
            async with httpx.AsyncClient(trust_env=False) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/api/v1/coding/jobs/{job_id}",
                    timeout=10
                )
                if resp.status_code in (200, 422):
                    return resp.json()["data"]
        
        raise TimeoutError("编码提取超时")
```

### 前端调用

```typescript
// api/coding.ts
export async function extractCoding(medicalText: string, age: number, gender: string) {
  // 通过后端代理调用
  const resp = await http.post('/api/v1/coding/extract-proxy', {
    text: medicalText,
    patient: { age, gender }
  })
  return resp.data
}
```

---

## 9. 测试脚本

```bash
# 运行测试
cd /home/ubuntu/coding/health-qc-monorepo/DRG
python3 test_coding_api.py
```

测试结果见: [CODING_API_TEST_REPORT.md](./CODING_API_TEST_REPORT.md)
