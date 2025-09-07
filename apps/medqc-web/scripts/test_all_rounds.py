#!/usr/bin/env python3
"""
专门测试查房记录识别的完整性
验证是否能识别到所有的查房记录
"""

import json
import re
from datetime import datetime
import os

def load_complete_record():
    """加载完整病程记录"""
    record_file = os.path.join(os.path.dirname(__file__), '..', 'backend', '张伟_病程记录.txt')
    
    with open(record_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    return content

def find_all_rounds(text):
    """查找所有查房记录"""
    print("🔍 扫描所有查房记录...")
    
    lines = text.split('\n')
    rounds = []
    
    # 查房记录的模式
    round_patterns = [
        r'.*查房记录',
        r'.*医师查房',
        r'.*主任.*查房',
        r'.*主治.*查房',
        r'.*副主任.*查房'
    ]
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # 检查是否包含查房相关内容
        for pattern in round_patterns:
            if re.search(pattern, line_stripped):
                # 提取时间信息
                time_match = re.search(r'(\d{4}年\d{2}月\d{2}日|\d{4}年\d{1,2}月\d{1,2}日)', line_stripped)
                if not time_match:
                    # 尝试另一种时间格式
                    time_match = re.search(r'(\d{4}年\d{2}月\d{2}日\d{2}时\d{2}分)', line_stripped)
                
                # 提取医师信息
                doctor_match = re.search(r'([^0-9\s]+(?:主任|主治|副主任).*?医师)', line_stripped)
                
                round_info = {
                    'line_number': i + 1,
                    'content': line_stripped,
                    'time': time_match.group(1) if time_match else '时间未识别',
                    'doctor': doctor_match.group(1) if doctor_match else '医师未识别',
                    'type': classify_round_type(line_stripped)
                }
                
                rounds.append(round_info)
                break
    
    return rounds

def classify_round_type(line):
    """分类查房类型"""
    if '主任' in line:
        return 'director_round'  # 主任查房
    elif '主治' in line:
        return 'attending_round'  # 主治医师查房
    elif '副主任' in line:
        return 'associate_director_round'  # 副主任查房
    elif '术前' in line:
        return 'preoperative_round'  # 术前查房
    elif '术后' in line:
        return 'postoperative_round'  # 术后查房
    else:
        return 'general_round'  # 一般查房

def extract_round_content(text, line_number, max_lines=10):
    """提取查房记录的详细内容"""
    lines = text.split('\n')
    start_idx = line_number - 1  # 转换为0基索引
    
    # 提取查房记录内容（从标题行开始，向下取若干行）
    content_lines = []
    for i in range(start_idx, min(start_idx + max_lines, len(lines))):
        line = lines[i].strip()
        if line:
            content_lines.append(line)
            # 如果遇到下一个时间标记，停止
            if i > start_idx and re.search(r'\d{4}年\d{2}月\d{2}日', line):
                break
    
    return '\n'.join(content_lines)

def enhanced_round_classification(text):
    """增强版查房记录分类"""
    print("\n🔍 执行增强版查房记录识别...")
    
    rounds = find_all_rounds(text)
    classified_rounds = []
    
    for round_info in rounds:
        # 提取详细内容
        detailed_content = extract_round_content(text, round_info['line_number'])
        
        # 计算置信度
        confidence = calculate_round_confidence(round_info['content'], detailed_content)
        
        classified_round = {
            "title": f"{round_info['doctor']}查房记录",
            "category": "progress_note",
            "type": "attending_progress",
            "confidence": confidence,
            "content": detailed_content,
            "summary": generate_round_summary(round_info, detailed_content),
            "position": {
                "line_number": round_info['line_number'],
                "time": round_info['time'],
                "doctor": round_info['doctor'],
                "round_type": round_info['type']
            },
            "metadata": {
                "round_sequence": len(classified_rounds) + 1,
                "round_type": round_info['type']
            }
        }
        
        classified_rounds.append(classified_round)
        
        print(f"   ✅ 第{len(classified_rounds)}次查房: {round_info['time']} - {round_info['doctor']} (置信度: {confidence:.2f})")
    
    return classified_rounds

def calculate_round_confidence(title_line, content):
    """计算查房记录的置信度"""
    confidence = 0.7  # 基础置信度
    
    # 如果有明确的时间信息
    if re.search(r'\d{4}年\d{2}月\d{2}日', title_line):
        confidence += 0.1
    
    # 如果有医师姓名
    if re.search(r'[^0-9\s]+(?:主任|主治|副主任)', title_line):
        confidence += 0.1
    
    # 如果内容包含医疗术语
    medical_terms = ['患者', '诊断', '治疗', '手术', '病情', '查体', '指示']
    term_count = sum(1 for term in medical_terms if term in content)
    confidence += min(term_count * 0.02, 0.1)
    
    return min(confidence, 0.98)

def generate_round_summary(round_info, content):
    """生成查房记录摘要"""
    doctor = round_info['doctor']
    time = round_info['time']
    
    # 从内容中提取关键信息
    if '术前' in content:
        return f"{doctor}于{time}进行术前查房，评估手术准备情况"
    elif '术后' in content:
        return f"{doctor}于{time}进行术后查房，评估术后恢复情况"
    elif '出院' in content:
        return f"{doctor}于{time}进行出院前查房，评估出院条件"
    else:
        return f"{doctor}于{time}进行常规查房，评估患者病情"

def generate_rounds_report(rounds):
    """生成查房记录报告"""
    print("\n" + "="*70)
    print("📋 完整查房记录识别报告")
    print("="*70)
    
    print(f"📊 总体统计:")
    print(f"   识别查房次数: {len(rounds)} 次")
    print(f"   平均置信度: {sum(r['confidence'] for r in rounds) / len(rounds):.3f}")
    
    # 按时间顺序排序
    rounds_sorted = sorted(rounds, key=lambda x: x['position']['line_number'])
    
    print(f"\n📅 查房时间序列:")
    for i, round_record in enumerate(rounds_sorted, 1):
        pos = round_record['position']
        print(f"   {i}. {pos['time']} - {pos['doctor']}")
        print(f"      类型: {pos['round_type']} | 置信度: {round_record['confidence']:.2f}")
        print(f"      摘要: {round_record['summary']}")
        print()
    
    # 统计医师查房次数
    doctor_stats = {}
    for round_record in rounds:
        doctor = round_record['position']['doctor']
        if doctor not in doctor_stats:
            doctor_stats[doctor] = 0
        doctor_stats[doctor] += 1
    
    print(f"👨‍⚕️ 医师查房统计:")
    for doctor, count in sorted(doctor_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {doctor}: {count} 次")
    
    return {
        'total_rounds': len(rounds),
        'average_confidence': sum(r['confidence'] for r in rounds) / len(rounds),
        'doctor_stats': doctor_stats,
        'rounds_by_type': {}
    }

def main():
    """主测试函数"""
    print("🏥 完整查房记录识别测试")
    print("=" * 50)
    print("目标: 识别病程记录中的所有查房记录")
    print("=" * 50)
    
    # 1. 加载病程记录
    record_content = load_complete_record()
    print(f"✅ 加载病程记录: {len(record_content)} 字符, {len(record_content.split(chr(10)))} 行")
    
    # 2. 查找所有查房记录
    all_rounds = find_all_rounds(record_content)
    print(f"🔍 发现查房记录: {len(all_rounds)} 次")
    
    # 3. 执行增强分类
    classified_rounds = enhanced_round_classification(record_content)
    
    # 4. 生成报告
    stats = generate_rounds_report(classified_rounds)
    
    # 5. 保存结果
    results = {
        "test_info": {
            "test_name": "完整查房记录识别测试",
            "patient_name": "方珍华",
            "test_date": datetime.now().isoformat(),
            "total_rounds_found": len(classified_rounds)
        },
        "rounds": classified_rounds,
        "statistics": stats
    }
    
    output_file = os.path.join(os.path.dirname(__file__), 'all_rounds_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 6. 结论
    print("\n" + "="*70)
    print("🎯 查房记录识别测试结论")
    print("="*70)
    
    total_found = len(classified_rounds)
    avg_confidence = stats['average_confidence']
    
    print(f"✅ 总查房记录数: {total_found} 次")
    print(f"✅ 平均置信度: {avg_confidence:.3f}")
    
    if total_found >= 5:
        print("🎉 成功识别5次以上查房记录！")
        grade = "优秀"
    elif total_found >= 3:
        print("✅ 识别了多次查房记录")
        grade = "良好"
    else:
        print("⚠️ 查房记录识别不完整")
        grade = "待改进"
    
    print(f"\n📈 识别效果: {grade}")
    print(f"💾 详细结果保存到: {output_file}")
    
    return results

if __name__ == "__main__":
    main()
