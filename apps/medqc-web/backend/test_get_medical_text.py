"""直接测试 _get_medical_text 函数，验证数据库查询是否返回真实数据"""
import asyncio
from app.services.frontpage_extraction_service import FrontPageExtractionService

async def main():
    service = FrontPageExtractionService()
    visit_id = "BA20260035"
    print(f"测试 _get_medical_text('{visit_id}')...")
    
    text = await service._get_medical_text(visit_id)
    
    print(f"\n长度: {len(text)} 字符")
    print(f"前500字符:\n{'='*60}")
    print(text[:500])
    print(f"{'='*60}")
    
    if "小磊" in text:
        print("\n✅ 包含 '小磊' — 从数据库获取了正确数据！")
    elif "张伟" in text:
        print("\n❌ 包含 '张伟' — 回退到了 demo 数据！")
    else:
        print("\n⚠️  既不包含 '小磊' 也不包含 '张伟'")

if __name__ == "__main__":
    asyncio.run(main())
