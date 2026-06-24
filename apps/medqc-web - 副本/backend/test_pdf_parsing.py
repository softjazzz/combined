#!/usr/bin/env python3
"""
测试PDF解析功能
"""

import sys
import os
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from services.pdf_parser import parse_pdf_file

def test_pdf_parsing():
    """测试PDF解析功能"""
    print("🔍 测试PDF解析功能")
    print("=" * 50)
    
    # 查找测试PDF文件
    test_files = [
        Path(__file__).parent.parent.parent / "张伟_病程记录.pdf",
        Path(__file__).parent.parent / "test_files" / "sample.pdf",
        Path(__file__).parent / "test.pdf",
        Path(__file__).parent / "test_sample.pdf"  # 添加示例文件路径
    ]
    
    pdf_file = None
    for file_path in test_files:
        if file_path.exists():
            pdf_file = file_path
            break
    
    if not pdf_file:
        print("❌ 没有找到测试PDF文件")
        print("请将PDF文件放在以下位置之一：")
        for file_path in test_files:
            print(f"  - {file_path}")
        return False
    
    print(f"📄 测试文件: {pdf_file}")
    print(f"📏 文件大小: {pdf_file.stat().st_size} bytes")
    
    try:
        # 读取文件内容
        with open(pdf_file, 'rb') as f:
            file_content = f.read()
        
        # 解析PDF
        print("\n🔄 开始解析PDF...")
        result = parse_pdf_file(file_content, pdf_file.name)
        
        # 显示结果
        print(f"\n✅ 解析结果:")
        print(f"  - 成功: {result['success']}")
        print(f"  - 方法: {result.get('method', 'N/A')}")
        print(f"  - 页数: {result.get('pages', 0)}")
        print(f"  - 内容长度: {len(result.get('content', ''))}")
        
        if result.get('error'):
            print(f"  - 错误: {result['error']}")
        
        # 显示提取的医疗信息
        medical_info = result.get('medical_info', {})
        if medical_info:
            print(f"\n🏥 提取的医疗信息:")
            for key, value in medical_info.items():
                if value:
                    print(f"  - {key}: {value}")
        
        # 显示内容预览
        content = result.get('content', '')
        if content:
            print(f"\n📝 内容预览 (前500字符):")
            print("-" * 30)
            print(content[:500])
            if len(content) > 500:
                print("...(内容已截断)")
            print("-" * 30)
        
        return result['success']
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

def create_sample_pdf():
    """创建一个示例PDF文件用于测试"""
    try:
        import fitz  # PyMuPDF
        
        # 创建一个简单的PDF文档
        doc = fitz.open()
        page = doc.new_page()
        
        # 添加医疗文本内容
        medical_text = """
        患者基本信息：
        姓名：张三
        性别：男
        年龄：65岁
        科室：心内科
        病历号：2024001

        入院记录：
        患者张三，男，65岁，因"胸闷、胸痛3天"于2024年8月28日入院。

        现病史：
        患者3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，持续时间约10-15分钟，休息后可缓解。
        伴有气短、乏力，无恶心、呕吐，无发热。

        既往史：
        高血压病史10年，规律服用降压药物。否认糖尿病、冠心病病史。

        体格检查：
        T：36.5℃，P：78次/分，R：18次/分，BP：140/90mmHg
        心界不大，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
        双肺呼吸音清，未闻及干湿性啰音。

        初步诊断：
        1. 不稳定性心绞痛
        2. 高血压病3级
        """
        
        # 插入文本 - 使用支持中文的字体
        try:
            # 尝试使用系统中文字体
            page.insert_text((50, 50), medical_text, fontsize=12, fontname="china-s")
        except:
            # 如果中文字体不可用，使用默认字体
            page.insert_text((50, 50), medical_text, fontsize=12)
        
        # 保存PDF
        output_path = Path(__file__).parent / "test_sample.pdf"
        doc.save(str(output_path))
        doc.close()
        
        print(f"✅ 创建示例PDF文件: {output_path}")
        return output_path
        
    except ImportError:
        print("❌ 无法创建示例PDF：PyMuPDF未安装")
        return None
    except Exception as e:
        print(f"❌ 创建示例PDF失败: {str(e)}")
        return None

if __name__ == "__main__":
    print("🧪 PDF解析功能测试")
    print("=" * 50)
    
    # 先尝试测试现有文件
    success = test_pdf_parsing()
    
    if not success:
        print("\n📝 尝试创建示例PDF文件...")
        sample_file = create_sample_pdf()
        if sample_file:
            print(f"\n🔄 使用示例文件重新测试...")
            # 重新测试
            success = test_pdf_parsing()
    
    if success:
        print("\n🎉 PDF解析功能测试通过！")
    else:
        print("\n❌ PDF解析功能测试失败！")
    
    print("\n" + "=" * 50)
