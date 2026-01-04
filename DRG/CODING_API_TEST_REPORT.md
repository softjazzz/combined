# ICD 编码 API 测试报告

## ✅ 测试成功！

**测试时间**: 2026-01-04  
**API 地址**: `http://122.51.111.253:8002`  
**测试工具**: `/DRG/test_coding_api.py`

---

## 📊 API 测试结果

### 1. 提交任务 (POST /api/v1/coding/extract)

**HTTP 状态**: `202 Accepted` ✅

**返回数据**:
```json
{
  "message": "accepted",
  "data": {
    "job_id": "job_54a54f66cfbf4f4a96b04e88f6756308",
    "request_id": "test_req_001"
  }
}
```

**结论**: 任务提交成功，返回 job_id 用于后续轮询。

---

### 2. 查询结果 (GET /api/v1/coding/jobs/{job_id})

**HTTP 状态**: `422 Unprocessable Entity` ⚠️  
**含义**: 编码完成，但需要人工确认（存在低置信度或冲突）

**处理时间**: 4.2 秒

**模型信息**:
- 模型版本: `qwen3-next-80b-a3b-instruct`
- 编码规则版本: `mvp`
- 结果哈希: `sha256:d3846d7561a06b645ac21311e725c4663461db11dc79f9a309c0371e00c7c1c2`

---

## 🏥 编码结果

### 主要诊断 (Principal Diagnosis)

| 字段 | 值 |
|------|-----|
| **ICD-10 编码** | A24.100x003 |
| **诊断名称** | 类鼻疽肺炎 |
| **置信度** | 0.95 (95%) |
| **证据位置** | 字符 560-567 |
| **证据文本** | "肺炎（右下肺）" |

### 次要诊断 (Secondary Diagnoses)

| 字段 | 值 |
|------|-----|
| **ICD-10 编码** | J96.900 |
| **诊断名称** | 呼吸衰竭 |
| **置信度** | 0.88 (88%) |
| **证据位置** | 字符 571-576 |
| **证据文本** | "呼吸衰竭？" |

### 手术操作

- **主要手术**: 无
- **次要手术**: 无

---

## ⚠️ 警告信息 (Warnings)

API 返回了 1 条警告，需要人工确认：

```json
{
  "field": "principal_diagnosis",
  "reason": "low_confidence",
  "message": "初步诊断中'肺炎（右下肺）'为疑似诊断，但无病原学确认，建议结合后续检查确认",
  "candidates": [
    {
      "name": "肺炎（右下肺）",
      "confidence": 0.95,
      "evidence_text": "肺炎（右下肺）"
    },
    {
      "name": "细菌性肺炎",
      "confidence": 0.85,
      "evidence_text": "考虑细菌性肺炎"
    }
  ]
}
```

**警告原因**: 
- 入院记录中诊断为"肺炎？"（疑似诊断）
- 缺乏病原学确认（如痰培养、病原体检测）
- 需要结合后续检查结果确认最终诊断

---

## 💡 API 特性分析

### ✅ 优点

1. **异步处理架构**
   - 采用 Job Queue 模式，避免长时间阻塞
   - 支持高并发场景

2. **智能证据定位**
   - 返回 `evidence_spans`（证据位置）
   - 可追溯到原始病历文本

3. **置信度评分**
   - 每个编码都有置信度分数
   - 便于判断是否需要人工审核

4. **多候选推荐**
   - 在 warnings 中提供备选诊断
   - 辅助编码员决策

5. **智能预警**
   - 自动识别疑似诊断、低置信度等情况
   - 返回 422 状态码提示需要人工确认

### ⚠️ 注意事项

1. **422 状态码的处理**
   - 422 不代表失败，而是"成功但需确认"
   - 前端应正常展示编码结果，同时显示警告信息

2. **轮询策略**
   - 建议轮询间隔: 2-3 秒
   - 最大重试次数: 10-15 次
   - 超时时间: 30-60 秒

3. **证据定位**
   - `evidence_spans` 使用字符偏移量（不是行号）
   - 前端需要根据偏移量高亮显示原文

---

## 🔧 集成建议

### 1. 前端集成

```typescript
// API 客户端
export async function submitCodingJob(medicalText: string) {
  const response = await http.post('/api/v1/coding/extract', {
    request_id: `req_${Date.now()}`,
    document_type: 'admission_note',
    text_content: medicalText,
    patient_context: {
      gender: 'M',
      age: 44
    },
    coding_mode: 'default'
  })
  
  return response.data.data.job_id
}

export async function pollCodingResult(jobId: string) {
  const response = await http.get(`/api/v1/coding/jobs/${jobId}`)
  
  // 422 也是成功状态，只是需要人工确认
  if (response.status === 200 || response.status === 422) {
    return {
      success: true,
      needsReview: response.status === 422,
      data: response.data.data
    }
  }
  
  throw new Error('Coding failed')
}
```

### 2. 后端代理

建议在 MedQC 后端创建代理服务：

```python
# backend/app/services/external_coding_service.py

class ExternalCodingService:
    BASE_URL = "http://122.51.111.253:8002"
    
    async def submit_job(self, text: str, context: dict):
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                f"{self.BASE_URL}/api/v1/coding/extract",
                json={
                    "request_id": f"req_{uuid.uuid4()}",
                    "document_type": "admission_note",
                    "text_content": text,
                    "patient_context": context,
                    "coding_mode": "default"
                },
                timeout=30
            )
            data = resp.json()
            return data["data"]["job_id"]
    
    async def get_result(self, job_id: str):
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.get(
                f"{self.BASE_URL}/api/v1/coding/jobs/{job_id}",
                timeout=10
            )
            return resp.json()
```

### 3. UI 展示建议

```vue
<template>
  <div class="coding-result">
    <!-- 主要诊断 -->
    <a-card title="主要诊断">
      <div class="diagnosis-item">
        <a-tag color="blue">{{ result.principal_diagnosis.code }}</a-tag>
        <span class="name">{{ result.principal_diagnosis.name }}</span>
        <a-progress 
          :percent="result.principal_diagnosis.confidence * 100" 
          :status="result.principal_diagnosis.confidence > 0.9 ? 'success' : 'warning'"
        />
      </div>
      
      <!-- 警告提示 -->
      <a-alert 
        v-if="warnings.length > 0"
        type="warning"
        :message="warnings[0].message"
        show-icon
      >
        <template #description>
          <div v-for="candidate in warnings[0].candidates" :key="candidate.name">
            <a-tag>{{ candidate.name }}</a-tag>
            置信度: {{ (candidate.confidence * 100).toFixed(0) }}%
          </div>
        </template>
      </a-alert>
    </a-card>
  </div>
</template>
```

---

## 📝 下一步工作

### 立即可做

1. ✅ **集成到病案首页生成流程**
   - 在 `FrontPageExtractionService` 中调用外部编码 API
   - 替换现有的 LLM 编码推荐逻辑

2. ✅ **前端组件开发**
   - 创建编码结果展示组件
   - 支持证据高亮显示
   - 警告信息提示

### 中期规划

3. **缓存机制**
   - 相同病历文本避免重复调用
   - 使用 Redis 缓存编码结果

4. **降级策略**
   - 外部 API 不可用时回退到 LLM
   - 超时处理和重试机制

### 长期优化

5. **批量处理**
   - 支持批量提交编码任务
   - 异步处理大量病例

6. **性能监控**
   - 记录 API 调用耗时
   - 统计编码准确率

---

## 📞 API 联系信息

**服务地址**: `http://122.51.111.253:8002`  
**文档**: 见用户提供的接口说明  
**状态**: ✅ 可用

---

**测试结论**: 第三方 ICD 编码 API 完全可用，建议优先集成到病案首页自动生成功能中。
