"""
DRG/DIP 功能性 API 测试
测试后端 API 的核心功能

运行方式:
    cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend
    source .venv/bin/activate
    pytest tests/test_drg_functional.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport

# 导入 FastAPI 应用
import sys
sys.path.insert(0, "/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend")
from app.main import app


# 配置 pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
async def async_client():
    """创建异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================
# DRG 分组 API 测试
# ============================================
class TestDRGGroupingAPI:
    """DRG 分组功能测试"""

    @pytest.mark.asyncio
    async def test_predict_realtime_basic(self, async_client):
        """测试实时 DRG 分组 - 基础请求"""
        response = await async_client.post("/api/v1/drg/predict-realtime", json={
            "primary_diagnosis_code": "I50.900",
            "secondary_diagnosis_codes": ["I10.x00", "I25.100"],
            "procedure_codes": [],
            "patient_age": 58,
            "patient_gender": "M",
            "region": "四川省"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        result = data["data"]
        
        # 验证返回结构
        assert "drg_code" in result
        assert "drg_name" in result
        assert "weight" in result
        assert "baseline_payment" in result
        
        # 验证数据有效性
        assert result["weight"] >= 0
        assert result["baseline_payment"] >= 0

    @pytest.mark.asyncio
    async def test_predict_realtime_with_procedure(self, async_client):
        """测试带手术编码的 DRG 分组"""
        response = await async_client.post("/api/v1/drg/predict-realtime", json={
            "primary_diagnosis_code": "K35.900",  # 急性阑尾炎
            "secondary_diagnosis_codes": [],
            "procedure_codes": ["47.01"],  # 阑尾切除术
            "patient_age": 32,
            "patient_gender": "M",
            "region": "四川省"
        })
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["drg_code"]  # 有分组编码

    @pytest.mark.asyncio
    async def test_predict_realtime_invalid_code(self, async_client):
        """测试无效诊断编码"""
        response = await async_client.post("/api/v1/drg/predict-realtime", json={
            "primary_diagnosis_code": "INVALID",
            "patient_age": 50,
            "patient_gender": "M",
            "region": "四川省"
        })
        
        # 应该返回降级结果而不是错误
        assert response.status_code == 200
        data = response.json()["data"]
        # 降级模式应有标识
        assert "drg_code" in data or "error" in data


# ============================================
# 病历抽取 API 测试
# ============================================
class TestFrontpageExtractionAPI:
    """病历抽取功能测试"""
    
    SAMPLE_MEDICAL_TEXT = """
入院记录

患者张三，男，58岁，因"反复胸闷、心悸3年，加重1周"于2026年1月1日入院。

现病史：患者3年前开始出现胸闷、心悸症状，活动后加重，休息后可缓解。
近1周上述症状加重，夜间阵发性呼吸困难，双下肢轻度水肿。

既往史：高血压病史10年，血压最高180/110mmHg，规律服用降压药物。

入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能III级
3. 高血压病3级

出院诊断：冠心病、心力衰竭、高血压病3级
"""

    @pytest.mark.asyncio
    async def test_auto_generate_draft(self, async_client):
        """测试自动生成病案首页草稿"""
        response = await async_client.post("/api/v1/frontpage/auto-generate-draft", json={
            "medical_text": self.SAMPLE_MEDICAL_TEXT
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success", True)  # 允许不同响应格式
        
        # 检查返回结构
        if "data" in data and "frontpage" in data["data"]:
            frontpage = data["data"]["frontpage"]
            # 验证有诊断信息
            assert "diagnoses" in frontpage or "basic_info" in frontpage

    @pytest.mark.asyncio
    async def test_auto_generate_draft_empty_text(self, async_client):
        """测试空文本处理"""
        response = await async_client.post("/api/v1/frontpage/auto-generate-draft", json={
            "medical_text": ""
        })
        
        # 应该返回错误或空结果
        assert response.status_code in [200, 400, 422]


# ============================================
# 批量数据 API 测试
# ============================================
class TestBatchDataAPI:
    """批量数据功能测试"""

    @pytest.mark.asyncio
    async def test_get_batches(self, async_client):
        """测试获取批次列表"""
        response = await async_client.get("/api/v1/drg/batches")
        
        assert response.status_code == 200
        data = response.json()
        assert "batches" in data
        assert isinstance(data["batches"], list)

    @pytest.mark.asyncio
    async def test_get_statistics(self, async_client):
        """测试获取统计数据"""
        response = await async_client.get("/api/v1/drg/statistics")
        
        assert response.status_code == 200
        data = response.json()
        # 验证统计结构
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_template_download(self, async_client):
        """测试模板下载"""
        response = await async_client.get("/api/v1/drg/template")
        
        assert response.status_code == 200
        # 验证是 Excel 文件
        assert "spreadsheet" in response.headers.get("content-type", "") or \
               "octet-stream" in response.headers.get("content-type", "")


# ============================================
# 导出 API 测试
# ============================================
class TestExportAPI:
    """导出功能测试"""

    @pytest.mark.asyncio
    async def test_export_excel(self, async_client):
        """测试 Excel 导出"""
        response = await async_client.get("/api/v1/drg/export/excel")
        
        # 可能返回文件或 404（无数据）
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_export_pdf(self, async_client):
        """测试 PDF 导出"""
        response = await async_client.get("/api/v1/drg/export/pdf")
        
        # 可能返回文件或 404（无数据）
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
