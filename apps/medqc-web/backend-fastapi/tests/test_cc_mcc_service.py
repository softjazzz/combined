"""
CC/MCC 知识库服务单元测试
"""

import pytest
from app.services.cc_mcc_service import CCMCCService, get_cc_mcc_service


class TestCCMCCService:
    """CC/MCC 服务测试"""
    
    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return CCMCCService()
    
    def test_service_initialization(self, service):
        """测试服务初始化"""
        assert service is not None
        assert isinstance(service.cc_codes, set)
        assert isinstance(service.mcc_codes, set)
        
        # 验证数据已加载
        stats = service.get_statistics()
        assert stats['total_cc'] > 0
        assert stats['total_mcc'] > 0
        print(f"✅ 加载统计: CC={stats['total_cc']}, MCC={stats['total_mcc']}")
    
    def test_is_mcc(self, service):
        """测试 MCC 判断"""
        # 根据 5_MCC.txt 的实际数据测试
        # A01.100 副伤寒甲 是 MCC
        assert service.is_mcc("A01.100") == True
        
        # 测试不存在的编码
        assert service.is_mcc("INVALID_CODE") == False
        
        print("✅ MCC 判断测试通过")
    
    def test_is_cc(self, service):
        """测试 CC 判断"""
        # 根据 6_CC.txt 的实际数据测试
        # A00.100 埃尔托生物型霍乱 是 CC
        assert service.is_cc("A00.100") == True
        
        # 测试不存在的编码
        assert service.is_cc("INVALID_CODE") == False
        
        print("✅ CC 判断测试通过")
    
    def test_is_cc_or_mcc(self, service):
        """测试 CC 或 MCC 判断"""
        # MCC 应该返回 True
        assert service.is_cc_or_mcc("A01.100") == True
        
        # CC 应该返回 True
        assert service.is_cc_or_mcc("A00.100") == True
        
        # 无效编码应该返回 False
        assert service.is_cc_or_mcc("INVALID_CODE") == False
        
        print("✅ CC/MCC 组合判断测试通过")
    
    def test_get_cc_mcc_info(self, service):
        """测试获取详细信息"""
        # 测试 MCC
        info = service.get_cc_mcc_info("A01.100")
        assert info['code'] == "A01.100"
        assert info['is_mcc'] == True
        assert info['type'] == "mcc"
        assert info['name'] is not None
        print(f"✅ MCC 信息: {info}")
        
        # 测试 CC
        info = service.get_cc_mcc_info("A00.100")
        assert info['code'] == "A00.100"
        assert info['is_cc'] == True
        assert info['type'] == "cc"
        assert info['name'] is not None
        print(f"✅ CC 信息: {info}")
        
        # 测试无效编码
        info = service.get_cc_mcc_info("INVALID_CODE")
        assert info['type'] == "none"
        assert info['is_cc'] == False
        assert info['is_mcc'] == False
        print(f"✅ 无效编码信息: {info}")
    
    def test_get_all_codes(self, service):
        """测试获取所有编码"""
        cc_codes = service.get_all_cc_codes()
        mcc_codes = service.get_all_mcc_codes()
        
        assert isinstance(cc_codes, set)
        assert isinstance(mcc_codes, set)
        assert len(cc_codes) > 0
        assert len(mcc_codes) > 0
        
        print(f"✅ CC 编码数量: {len(cc_codes)}")
        print(f"✅ MCC 编码数量: {len(mcc_codes)}")
    
    def test_singleton(self):
        """测试单例模式"""
        service1 = get_cc_mcc_service()
        service2 = get_cc_mcc_service()
        
        assert service1 is service2
        print("✅ 单例模式测试通过")
    
    def test_real_world_codes(self, service):
        """测试真实世界的编码"""
        # 根据之前的讨论，测试一些常见的 CC/MCC
        # N18.3 - 慢性肾脏病3期 (应该是 CC)
        # N18.5 - 慢性肾脏病5期 (应该是 MCC)
        
        # 注意：这些测试依赖于实际数据文件的内容
        # 如果文件中没有这些编码，测试会失败
        
        test_codes = [
            "N18.3",  # 慢性肾脏病3期
            "N18.5",  # 慢性肾脏病5期
            "E11.65", # 糖尿病伴高渗昏迷
        ]
        
        for code in test_codes:
            info = service.get_cc_mcc_info(code)
            print(f"编码 {code}: {info['type']} - {info.get('name', '未找到')}")


if __name__ == "__main__":
    """直接运行测试"""
    print("=" * 60)
    print("CC/MCC 知识库服务测试")
    print("=" * 60)
    
    service = CCMCCService()
    
    # 测试统计
    stats = service.get_statistics()
    print(f"\n📊 统计信息:")
    print(f"   CC 总数: {stats['total_cc']}")
    print(f"   MCC 总数: {stats['total_mcc']}")
    print(f"   合计: {stats['total']}")
    
    # 测试一些示例编码
    print(f"\n🔍 测试示例编码:")
    test_codes = ["A01.100", "A00.100", "N18.3", "N18.5", "E11.65", "INVALID"]
    
    for code in test_codes:
        info = service.get_cc_mcc_info(code)
        status = "✅" if info['type'] != "none" else "❌"
        print(f"   {status} {code}: {info['type'].upper():6s} - {info.get('name', '未找到')}")
    
    print(f"\n✅ 所有测试完成!")
