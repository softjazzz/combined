"""
精确修改 WorkstationV4View.vue：
1. 住院概览卡：深蓝渐变 -> 轻薄蓝50渐变（减重）
2. 患者信息行：divide-y 横线 -> 无线条，用 py 间距 + 字重对比区分层级
3. AI 生成首页按钮：添加发光效果
"""

path = r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\views\workstation-v2\WorkstationV4View.vue'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============= 修改 1：住院概览卡减重 =============
# 深蓝渐变 from-blue-500 to-indigo-600 -> 极轻蓝白渐变 + 深色文字
old_card = 'class="rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-4 text-white shadow-md shadow-blue-100 dark:shadow-blue-900/20"'
new_card = 'class="rounded-xl bg-gradient-to-br from-blue-50/90 to-indigo-50/60 border border-blue-100/80 dark:border-blue-900/40 dark:from-blue-950/40 dark:to-indigo-950/30 p-4 shadow-[0_2px_12px_rgba(59,130,246,0.06)]"'
content = content.replace(old_card, new_card, 1)

# 住院信息标题颜色：text-white -> text-blue-900/dark
old_title = '<span class="text-[11px] font-semibold opacity-70 uppercase tracking-widest">住院信息</span>'
new_title = '<span class="text-[11px] font-bold text-blue-800 dark:text-blue-300 uppercase tracking-widest">住院信息</span>'
content = content.replace(old_title, new_title, 1)

# 医保标签：bg-white/20 -> bg-blue-100/60 
old_badge = 'class="text-[11px] font-semibold bg-white/20 px-2 py-0.5 rounded-full"'
new_badge = 'class="text-[11px] font-semibold bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2.5 py-0.5 rounded-full"'
content = content.replace(old_badge, new_badge, 1)

# 入院 label：text-[10px] opacity-60 -> 浅灰
old_label1 = '<div class="text-[10px] opacity-60 mb-0.5">入院</div>'
new_label1 = '<div class="text-[10px] text-blue-500 dark:text-blue-400 mb-0.5 font-medium">入院</div>'
content = content.replace(old_label1, new_label1, 1)

# 入院日期：font-bold font-mono (白色变深蓝)
old_date1 = '<div class="text-sm font-bold font-mono">{{ selectedRecord.admissionDate || \'—\' }}</div>'
new_date1 = '<div class="text-sm font-extrabold font-mono text-blue-900 dark:text-blue-100">{{ selectedRecord.admissionDate || \'—\' }}</div>'
content = content.replace(old_date1, new_date1, 1)

# timeline 横线：bg-white/30 -> bg-blue-200/60
old_line = '<div class="flex-1 h-px bg-white/30"></div>'
new_line = '<div class="flex-1 h-px bg-blue-200/70 dark:bg-blue-700/40"></div>'
content = content.replace(old_line, new_line)  # 两处都换

# 住院天数数字：text-base font-black -> text-blue-900
old_days = '<div class="text-base font-black leading-none">{{ selectedRecord.days }}</div>'
new_days = '<div class="text-lg font-black leading-none text-blue-800 dark:text-blue-200">{{ selectedRecord.days }}</div>'
content = content.replace(old_days, new_days, 1)

# 天字：opacity-60 -> text-blue-400
old_days_label = '<div class="text-[9px] opacity-60 leading-none mt-0.5">天</div>'
new_days_label = '<div class="text-[9px] text-blue-400 leading-none mt-0.5 font-medium">天</div>'
content = content.replace(old_days_label, new_days_label, 1)

# 出院 label
old_label2 = '<div class="text-[10px] opacity-60 mb-0.5">出院</div>'
new_label2 = '<div class="text-[10px] text-blue-500 dark:text-blue-400 mb-0.5 font-medium">出院</div>'
content = content.replace(old_label2, new_label2, 1)

# 出院日期
old_date2 = '<div class="text-sm font-bold font-mono">{{ selectedRecord.dischargeDate || \'—\' }}</div>'
new_date2 = '<div class="text-sm font-extrabold font-mono text-slate-700 dark:text-slate-300">{{ selectedRecord.dischargeDate || \'—\' }}</div>'
content = content.replace(old_date2, new_date2, 1)

# 底部科室医生一行：border-white/20 -> border-blue-200/60
old_footer = 'class="flex items-center gap-3 pt-2 border-t border-white/20 text-[12px] opacity-80"'
new_footer = 'class="flex items-center gap-3 pt-2.5 border-t border-blue-100 dark:border-blue-800/50 text-[12px] text-slate-600 dark:text-slate-400"'
content = content.replace(old_footer, new_footer, 1)

# ============= 修改 2：患者信息行去掉 divide-y 横线，改为无线间距排版 =============
old_div_y = 'class="rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden divide-y divide-slate-50 dark:divide-slate-800"'
new_div_y = 'class="rounded-xl bg-white dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 overflow-hidden px-1"'
content = content.replace(old_div_y, new_div_y, 1)

# 行样式：px-3.5 py-2.5 -> 去横线改为纯间距
old_row = "class=\"flex items-center px-3.5 py-2.5\""
new_row = "class=\"flex items-center px-3 py-2\""
content = content.replace(old_row, new_row)

# label 颜色：text-slate-400 -> text-gray-400
old_label = 'class="text-[11px] text-slate-400 dark:text-slate-500 w-[72px] flex-shrink-0"'
new_label = 'class="text-[11px] text-gray-400 dark:text-slate-500 w-[72px] flex-shrink-0"'
content = content.replace(old_label, new_label)

# value 颜色：text-slate-700 -> text-gray-800 font-semibold
old_val = 'class="text-[13px] font-medium text-slate-700 dark:text-slate-200 truncate"'
new_val = 'class="text-[13px] font-semibold text-gray-800 dark:text-slate-200 truncate"'
content = content.replace(old_val, new_val)

# ============= 修改 3：AI 生成首页按钮发光效果 =============
old_btn = 'class="!rounded-lg"\n            >\n              <template #icon><ThunderboltOutlined /></template>\n              {{ frontpageDraft ? \'重新生成\' : \'AI 生成首页\' }}'
new_btn = 'class="!rounded-lg !shadow-[0_4px_14px_rgba(59,130,246,0.4)] hover:!shadow-[0_4px_20px_rgba(99,102,241,0.5)] transition-shadow duration-300"\n            >\n              <template #icon><ThunderboltOutlined /></template>\n              {{ frontpageDraft ? \'重新生成\' : \'AI 生成首页\' }}'
content = content.replace(old_btn, new_btn, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("WorkstationV4View.vue patched successfully")

# 验证替换
checks = [
    'from-blue-50/90',
    'border-blue-100/80',
    'text-blue-800',
    'bg-blue-100',
    'shadow-[0_4px_14px_rgba(59,130,246,0.4)',
]
for c in checks:
    found = c in content
    print(f"  {'OK' if found else 'MISS'}: {c}")
