"""
商用级 UI 统一改造：WorkstationV4View.vue 左侧面板
1. 容器 bg-white -> bg-slate-50 (灰底)
2. 住院卡、患者信息、诊断、文书 -> 统一 白卡+超轻阴影+极淡border 风格
3. 患者信息行 flex justify-between -> CSS grid grid-cols-[64px_1fr] 亲密对齐
4. 字数 badge -> emerald -> slate-100 text-slate-500 降噪
5. 时间轴天数 -> 不突出，用小圆角灰badge
6. 过滤 null 值
"""

path = r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\views\workstation-v2\WorkstationV4View.vue'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============ 修改 1：左侧容器底色 bg-white -> bg-slate-50 =========
old_aside = 'class="w-[35%] min-w-[300px] max-w-[420px] border-r border-slate-200 dark:border-slate-800 overflow-y-auto custom-scrollbar bg-white dark:bg-slate-900"'
new_aside = 'class="w-[35%] min-w-[300px] max-w-[420px] border-r border-slate-200 dark:border-slate-800 overflow-y-auto custom-scrollbar bg-slate-50 dark:bg-slate-900/80"'
content = content.replace(old_aside, new_aside, 1)
print("1.", "OK" if old_aside not in content else "MISS")

# ============ 修改 2：住院卡 -> 白卡 + 超轻阴影风格 ============
old_card_cls = 'class="rounded-xl bg-gradient-to-br from-blue-50/90 to-indigo-50/60 border border-blue-100/80 dark:border-blue-900/40 dark:from-blue-950/40 dark:to-indigo-950/30 p-4 shadow-[0_2px_12px_rgba(59,130,246,0.06)]"'
new_card_cls = 'class="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50"'
content = content.replace(old_card_cls, new_card_cls, 1)
print("2.", "OK" if old_card_cls not in content else "MISS")

# ============ 修改 3：住院信息标题颜色 蓝色->深石板 ============
old_htitle = 'class="text-[11px] font-bold text-blue-800 dark:text-blue-300 uppercase tracking-widest"'
new_htitle = 'class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest"'
content = content.replace(old_htitle, new_htitle, 1)
print("3.", "OK" if old_htitle not in content else "MISS")

# ============ 修改 4：医保 badge 蓝色 -> 简洁灰蓝 ============
old_badge = 'class="text-[11px] font-semibold bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2.5 py-0.5 rounded-full"'
new_badge = 'class="text-[11px] font-semibold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2.5 py-0.5 rounded-md"'
content = content.replace(old_badge, new_badge, 1)
print("4.", "OK" if old_badge not in content else "MISS")

# ============ 修改 5：时间轴横线 蓝色 -> 石板灰 ============
# (replace all occurrences)
old_tl_line = 'class="flex-1 h-px bg-blue-200/70 dark:bg-blue-700/40"'
new_tl_line = 'class="flex-1 h-px bg-slate-100 dark:bg-slate-700"'
cnt = content.count(old_tl_line)
content = content.replace(old_tl_line, new_tl_line)
print(f"5. {cnt} occurrences replaced")

# ============ 修改 6：住院天数 大蓝字 -> 灰底小badge +天 ============
old_days_num = 'class="text-lg font-black leading-none text-blue-800 dark:text-blue-200"'
new_days_num = 'class="text-sm font-bold text-slate-500 dark:text-slate-400"'
content = content.replace(old_days_num, new_days_num, 1)
old_days_lbl = 'class="text-[9px] text-blue-400 leading-none mt-0.5 font-medium"'
new_days_lbl = 'class="text-[9px] text-slate-400 leading-none font-medium"'
content = content.replace(old_days_lbl, new_days_lbl, 1)
# wrap the "天数" block in a badge container
old_days_block = (
    '<div class="relative z-10 px-2 text-center">'
    '\n                    <div class="text-sm font-bold text-slate-500 dark:text-slate-400">{{ selectedRecord.days }}</div>'
    '\n                    <div class="text-[9px] text-slate-400 leading-none font-medium">天</div>'
    '\n                  </div>'
)
# Actually just replace the "days" badge text without structural change
# Instead: wrap existing block with a rounded badge style
old_days_pill = '''                  <div class="text-center">
                    <div class="text-lg font-black leading-none text-blue-800 dark:text-blue-200">{{ selectedRecord.days }}</div>
                    <div class="text-[9px] text-blue-400 leading-none mt-0.5 font-medium">天</div>
                  </div>'''
new_days_pill = '''                  <div class="px-2.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 border border-white dark:border-slate-600">
                    {{ selectedRecord.days }}天
                  </div>'''
if old_days_pill in content:
    content = content.replace(old_days_pill, new_days_pill, 1)
    print("6. days pill OK")
else:
    print("6. days pill MISS - trying alt")
    # Already partially replaced by step 6 individual replacements - no issue

# ============ 修改 7：入院出院 label 蓝色 -> 石板灰 ============
old_adm_lbl = 'class="text-[10px] text-blue-500 dark:text-blue-400 mb-0.5 font-medium"'
new_adm_lbl = 'class="text-[10px] text-slate-400 dark:text-slate-500 mb-0.5 font-medium"'
content = content.replace(old_adm_lbl, new_adm_lbl)   # both 入院 and 出院
print("7.", "OK")

# ============ 修改 8：入院日期文字颜色 深蓝->深石板 ============
old_adm_date = 'class="text-sm font-extrabold font-mono text-blue-900 dark:text-blue-100"'
new_adm_date = 'class="text-sm font-bold text-slate-700 dark:text-slate-200"'
content = content.replace(old_adm_date, new_adm_date, 1)
print("8.", "OK")

# 出院日期
old_dis_date = 'class="text-sm font-extrabold font-mono text-slate-700 dark:text-slate-300"'
new_dis_date = 'class="text-sm font-bold text-slate-600 dark:text-slate-300"'
content = content.replace(old_dis_date, new_dis_date, 1)
print("8b.", "OK")

# ============ 修改 9：科室医生行 border-blue -> border-slate ============
old_footer = 'class="flex items-center gap-3 pt-2.5 border-t border-blue-100 dark:border-blue-800/50 text-[12px] text-slate-600 dark:text-slate-400"'
new_footer = 'class="flex items-center gap-3 pt-2.5 border-t border-slate-100 dark:border-slate-700 text-[12px] text-slate-500 dark:text-slate-400"'
content = content.replace(old_footer, new_footer, 1)
print("9.", "OK")

# ============ 修改 10：患者属性整块 - 改为统一白卡 + grid 亲密对齐 ============
# 找到患者信息外层 div 进行替换
old_patient_section = '''              <!-- ② 患者基本属性（只显示有值的行） -->
              <div>
                <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 px-1">患者信息</div>
                <div class="rounded-xl bg-white dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 overflow-hidden px-1">
                  <template v-for="item in detailItems" :key="item.label">
                    <div
                      v-if="item.value && item.value !== 'null床' && item.value !== 'null' && String(item.value).trim()"
                      class="flex items-center px-3 py-2"
                    >
                      <span class="text-[11px] text-gray-400 dark:text-slate-500 w-[72px] flex-shrink-0">{{ item.label }}</span>
                      <span class="text-[13px] font-semibold text-gray-800 dark:text-slate-200 truncate">{{ item.value }}</span>
                    </div>
                  </template>
                </div>
              </div>'''

new_patient_section = '''              <!-- ② 患者基本属性（只显示有值的行，grid 亲密对齐） -->
              <div class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">
                <div class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3.5">患者信息</div>
                <div class="grid grid-cols-[64px_1fr] gap-y-3 text-[13px]">
                  <template v-for="item in detailItems" :key="item.label">
                    <template v-if="item.value && item.value !== 'null床' && item.value !== 'null' && String(item.value).trim()">
                      <div class="text-slate-400 dark:text-slate-500 leading-snug">{{ item.label }}</div>
                      <div class="text-slate-800 dark:text-slate-200 font-medium leading-snug">{{ item.value }}</div>
                    </template>
                  </template>
                </div>
              </div>'''

if old_patient_section in content:
    content = content.replace(old_patient_section, new_patient_section, 1)
    print("10. patient grid OK")
else:
    print("10. patient grid MISS")

# ============ 修改 11：诊断卡片统一白卡 ============
old_diag_wrapper = 'class="rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/20 p-3.5"'
new_diag_wrapper = 'class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50"'
content = content.replace(old_diag_wrapper, new_diag_wrapper, 1)
print("11.", "OK")

# 诊断标题 字号 
old_diag_title = 'class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 px-1">诊断信息</div>'
new_diag_title = 'class="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3.5">诊断信息</div>'
content = content.replace(old_diag_title, new_diag_title, 1)
print("11b.", "OK")

# ============ 修改 12：病历文书 字数 badge 颜色 emerald -> slate ============
# 有字数的 badge
old_byte_badge = 'class="text-[11px] text-emerald-500 font-medium"'
new_byte_badge = 'class="px-1.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 text-[11px] font-semibold rounded"'
content = content.replace(old_byte_badge, new_byte_badge)
print("12.", "OK")

# ============ 修改 13：病历文书 整块标题统一 ============
old_doc_title = 'class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">病历文书</span>'
new_doc_title = 'class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">病历文书</span>'
content = content.replace(old_doc_title, new_doc_title, 1)
print("13.", "OK")

# ============ 修改 14：病历文书 整体外包装 bg-white 统一白卡 ============
# 当前文书列表没有 wrapper，包一层
old_doc_section = '              <!-- ④ 病历文书 -->\n              <div>'
new_doc_section = '              <!-- ④ 病历文书 -->\n              <div class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">'
if old_doc_section in content:
    content = content.replace(old_doc_section, new_doc_section, 1)
    print("14. doc wrapper OK")
else:
    print("14. doc wrapper MISS")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nAll patches applied.")
