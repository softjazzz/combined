#!/usr/bin/env python3
"""
对比串行质控和快速质控两种模式的性能差异

数据来源：
- 串行模式：/tmp/qwen3_model_comparison_results.json
- 快速模式：/tmp/qwen3_fast_mode_results.json
"""

import json

# 加载数据
with open("/tmp/qwen3_model_comparison_results.json", "r", encoding="utf-8") as f:
    serial_results = json.load(f)

with open("/tmp/qwen3_fast_mode_results.json", "r", encoding="utf-8") as f:
    fast_results = json.load(f)

# 创建模型映射
serial_map = {r["model_code"]: r for r in serial_results}
fast_map = {r["model_code"]: r for r in fast_results}

print("=" * 100)
print("Qwen3 系列模型：串行质控 vs 快速质控 性能对比分析")
print("=" * 100)

print("\n📊 1. 响应时间对比")
print("-" * 100)
print(f"{'模型':30s} | {'串行模式':>10s} | {'快速模式':>10s} | {'加速比':>10s} | {'性能提升':>10s}")
print("-" * 100)

time_improvements = []
for model_code in serial_map.keys():
    if model_code in fast_map:
        serial_time = serial_map[model_code]["result"]["elapsed_time"]
        fast_time = fast_map[model_code]["result"]["elapsed_time"]
        speedup = serial_time / fast_time if fast_time > 0 else 0
        improvement = ((serial_time - fast_time) / serial_time * 100) if serial_time > 0 else 0
        time_improvements.append({
            "model": serial_map[model_code]["model_name"],
            "serial": serial_time,
            "fast": fast_time,
            "speedup": speedup,
            "improvement": improvement
        })
        
        print(f"{serial_map[model_code]['model_name']:30s} | {serial_time:9.2f}秒 | {fast_time:9.2f}秒 | {speedup:9.2f}x | {improvement:9.1f}%")

# 计算平均加速比
avg_speedup = sum(t["speedup"] for t in time_improvements) / len(time_improvements)
avg_improvement = sum(t["improvement"] for t in time_improvements) / len(time_improvements)
print("-" * 100)
print(f"{'平均':30s} | {'':>10s} | {'':>10s} | {avg_speedup:9.2f}x | {avg_improvement:9.1f}%")

print("\n💰 2. Token 消耗对比")
print("-" * 100)
print(f"{'模型':30s} | {'串行模式':>10s} | {'快速模式':>10s} | {'差异':>10s} | {'节省率':>10s}")
print("-" * 100)

token_savings = []
for model_code in serial_map.keys():
    if model_code in fast_map:
        serial_tokens = serial_map[model_code]["result"]["response"].get("performance_metrics", {}).get("token_usage", 0)
        fast_tokens = fast_map[model_code]["result"]["response"].get("performance_metrics", {}).get("token_usage", 0)
        diff = serial_tokens - fast_tokens
        saving_rate = (diff / serial_tokens * 100) if serial_tokens > 0 else 0
        token_savings.append({
            "model": serial_map[model_code]["model_name"],
            "serial": serial_tokens,
            "fast": fast_tokens,
            "diff": diff,
            "saving_rate": saving_rate
        })
        
        print(f"{serial_map[model_code]['model_name']:30s} | {serial_tokens:9d}T | {fast_tokens:9d}T | {diff:+9d}T | {saving_rate:9.1f}%")

# 计算平均节省率
avg_saving_rate = sum(t["saving_rate"] for t in token_savings) / len(token_savings)
print("-" * 100)
print(f"{'平均':30s} | {'':>10s} | {'':>10s} | {'':>10s} | {avg_saving_rate:9.1f}%")

print("\n🎯 3. LX-001 判定一致性对比")
print("-" * 100)
print(f"{'模型':30s} | {'串行模式':>10s} | {'快速模式':>10s} | {'一致性':>10s}")
print("-" * 100)

consistency_count = 0
total_count = 0
for model_code in serial_map.keys():
    if model_code in fast_map:
        # 获取串行模式的 LX-001 判定
        serial_eval = serial_map[model_code]["result"]["response"].get("evaluation_results", [])
        serial_lx001 = None
        for r in serial_eval:
            if r.get("rule_id") == "LX-001":
                serial_lx001 = "合规" if r.get("is_compliant") else "不合规"
                break
        
        # 获取快速模式的 LX-001 判定
        fast_eval = fast_map[model_code]["result"]["response"].get("evaluation_results", [])
        fast_lx001 = None
        for r in fast_eval:
            if r.get("rule_id") == "LX-001":
                fast_lx001 = "合规" if r.get("is_compliant") else "不合规"
                break
        
        is_consistent = serial_lx001 == fast_lx001
        if is_consistent:
            consistency_count += 1
        total_count += 1
        
        consistency_mark = "✅ 一致" if is_consistent else "❌ 不一致"
        print(f"{serial_map[model_code]['model_name']:30s} | {serial_lx001 or 'N/A':>10s} | {fast_lx001 or 'N/A':>10s} | {consistency_mark:>10s}")

print("-" * 100)
print(f"一致性统计: {consistency_count}/{total_count} = {consistency_count/total_count*100:.1f}%")

print("\n📈 4. 综合性能对比")
print("-" * 100)

# 找出最佳模型
best_serial_time = min(time_improvements, key=lambda x: x["serial"])
best_fast_time = min(time_improvements, key=lambda x: x["fast"])
best_speedup = max(time_improvements, key=lambda x: x["speedup"])
best_token_saving = max(token_savings, key=lambda x: x["saving_rate"])

print(f"⚡ 串行模式最快: {best_serial_time['model']} ({best_serial_time['serial']:.2f}秒)")
print(f"⚡ 快速模式最快: {best_fast_time['model']} ({best_fast_time['fast']:.2f}秒)")
print(f"🚀 最大加速比: {best_speedup['model']} ({best_speedup['speedup']:.2f}x)")
print(f"💰 最大Token节省: {best_token_saving['model']} ({best_token_saving['saving_rate']:.1f}%)")

print("\n🏆 5. 推荐结论")
print("-" * 100)

print(f"""
✅ 快速质控模式优势：
   - 平均加速比: {avg_speedup:.2f}x（提升 {avg_improvement:.1f}%）
   - 平均Token节省: {avg_saving_rate:.1f}%
   - 最快响应: {best_fast_time['model']} ({best_fast_time['fast']:.2f}秒)
   
⚠️  快速质控模式劣势：
   - LX-001 判定一致性: {consistency_count/total_count*100:.1f}%
   - 部分模型判定结果与串行模式不同
   
💡 推荐策略：
   1. 生产环境：使用快速质控模式（性能提升显著）
   2. 选择判定一致的模型：
""")

# 列出判定一致的模型
consistent_models = []
for model_code in serial_map.keys():
    if model_code in fast_map:
        serial_eval = serial_map[model_code]["result"]["response"].get("evaluation_results", [])
        serial_lx001 = None
        for r in serial_eval:
            if r.get("rule_id") == "LX-001":
                serial_lx001 = r.get("is_compliant")
                break
        
        fast_eval = fast_map[model_code]["result"]["response"].get("evaluation_results", [])
        fast_lx001 = None
        for r in fast_eval:
            if r.get("rule_id") == "LX-001":
                fast_lx001 = r.get("is_compliant")
                break
        
        if serial_lx001 == fast_lx001:
            # 找到对应的性能数据
            perf = next((t for t in time_improvements if t["model"] == serial_map[model_code]["model_name"]), None)
            if perf:
                consistent_models.append({
                    "name": serial_map[model_code]["model_name"],
                    "fast_time": perf["fast"],
                    "speedup": perf["speedup"]
                })

# 按快速模式响应时间排序
consistent_models.sort(key=lambda x: x["fast_time"])

for i, m in enumerate(consistent_models[:3], 1):
    print(f"      {i}. {m['name']} - {m['fast_time']:.2f}秒 ({m['speedup']:.2f}x 加速)")

print(f"""
   3. 对于需要高准确性的场景：使用串行模式
   4. 对于需要高性能的场景：使用快速模式
""")

print("=" * 100)
print("分析完成！")
print("=" * 100)

