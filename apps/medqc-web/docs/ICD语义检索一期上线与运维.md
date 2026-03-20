# ICD 语义检索一期上线与运维

## 1. 目标
- 场景：`/extract`、`/auto-generate-draft-stream` 诊断编码兜底召回。
- 路径：`精确匹配 -> 归一化匹配 -> 语义召回(faiss) -> 阈值决策`。

## 2. 依赖
- 后端依赖已加入：`faiss-cpu>=1.8.0,<2.0.0`。
- 安装：
```bash
cd backend
py -3.10 -m pip install -r requirements.txt
```

## 3. 配置
在 `backend/.env`：
```env
ICD_SEMANTIC_ENABLED=true
ICD_SEMANTIC_BACKEND=faiss
ICD_SEMANTIC_INDEX_DIR=data/vector
ICD_SEMANTIC_EMBED_MODEL=BAAI/bge-m3
ICD_SEMANTIC_API_ENDPOINT=https://api.siliconflow.cn/v1/embeddings
ICD_SEMANTIC_API_KEY=你的key
ICD_SEMANTIC_TOP_K=5
ICD_SEMANTIC_T_HIGH=0.90
ICD_SEMANTIC_T_LOW=0.60
```

## 4. 构建索引（全量）
```bash
cd backend
py -3.10 scripts/build_icd_vector_index.py --engine faiss --batch-size 64
```

产物目录（默认）：
- `backend/data/vector/icd10_vectors.npy`
- `backend/data/vector/icd10_meta.json`
- `backend/data/vector/icd10.faiss`

## 5. 烟测
```bash
cd backend
py -3.10 -m pytest tests/unit/test_local_icd_semantic.py -q
```

可额外验证：
- `冠脉支架植入后状态 -> Z95.501`
- 低置信候选仅回传到 `*_icd_suggestions`，不自动落码

## 6. 运行与回滚
- 启用：`ICD_SEMANTIC_ENABLED=true`
- 回滚：`ICD_SEMANTIC_ENABLED=false`（立即退回纯本地精确/模糊匹配）
- 索引异常时可重建第 4 步。

## 7. 一期阈值建议
- `T_HIGH=0.90`：自动填码，误码风险较低
- `T_LOW=0.60`：候选建议可见，人工可判读
