#!/usr/bin/env python3
"""
创建包含真实医疗内容的测试PDF文件
"""

import fitz  # PyMuPDF
from pathlib import Path

def create_medical_pdf():
    """创建医疗PDF文件"""
    
    # 医疗内容
    medical_content = """患者基本信息：
姓名：张伟
性别：男
年龄：45岁
科室：内科
病历号：2024002

病程记录：
患者张伟，男，45岁，因"发热、咳嗽5天"入院。

现病史：
患者5天前出现发热，体温最高39.2℃，伴有咳嗽、咳痰，痰液为白色粘痰。
无胸痛、胸闷，无恶心、呕吐，无腹痛、腹泻。
既往体健，否认高血压、糖尿病、冠心病等慢性疾病史。

体格检查：
T：38.5℃，P：88次/分，R：20次/分，BP：120/80mmHg
神志清楚，精神可，营养状态良好。
心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
双肺可闻及湿性啰音，以双下肺为著。
腹部平软，无压痛反跳痛，肝脾肋下未触及。

辅助检查：
血常规：WBC 12.5×10^9/L，N 78%，RBC 4.2×10^12/L，Hb 135g/L
胸部X线：双肺纹理增粗，双下肺可见片状阴影
痰培养：肺炎链球菌阳性

初步诊断：
1. 肺炎
2. 发热待查

治疗方案：
1. 抗感染治疗：头孢曲松钠2.0g静滴，每日1次
2. 对症支持治疗：退热、止咳、化痰
3. 密切观察病情变化，监测体温、血象
4. 适当休息，加强营养

医师签名：李医生
日期：2024年8月28日"""

    try:
        # 创建PDF文档
        doc = fitz.open()
        page = doc.new_page()
        
        # 设置字体和大小
        font_size = 12
        line_height = 16
        margin_left = 50
        margin_top = 50
        
        # 分行处理文本
        lines = medical_content.split('\n')
        y_position = margin_top
        
        for line in lines:
            if line.strip():  # 非空行
                # 插入文本，使用默认字体（支持中文）
                page.insert_text(
                    (margin_left, y_position), 
                    line, 
                    fontsize=font_size,
                    color=(0, 0, 0)  # 黑色
                )
            y_position += line_height
            
            # 如果超出页面，创建新页面
            if y_position > 750:  # 页面高度限制
                page = doc.new_page()
                y_position = margin_top
        
        # 保存PDF
        output_path = Path(__file__).parent / "张伟_病程记录.pdf"
        doc.save(str(output_path))
        doc.close()
        
        print(f"✅ 成功创建医疗PDF文件: {output_path}")
        print(f"📄 文件大小: {output_path.stat().st_size} bytes")
        
        return output_path
        
    except Exception as e:
        print(f"❌ 创建PDF失败: {str(e)}")
        return None

if __name__ == "__main__":
    create_medical_pdf()



