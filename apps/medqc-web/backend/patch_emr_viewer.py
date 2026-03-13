"""
精确重写 EMRViewer.vue 的模板区域（行范围替换）
"""
import sys

path = r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\components\qc\EMRViewer.vue'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 新内容（替换第 4~56 行，即 index 3~55，template 区的文书Tab + 工具栏 + 内容区）
# 保留 line 1-3 和 line 57+ 的其他内容不变
# 用 \r\n 因为原文件是 CRLF
R = '\r\n'

new_section = (
    f'    <!-- 文书标签页（胶囊 Pill 样式） -->{R}'
    f'    <div v-if="documents.length > 1" class="mb-5">{R}'
    f'      <div class="inline-flex items-center gap-1 bg-gray-100/80 p-1 rounded-xl border border-gray-100/50">{R}'
    f'        <button{R}'
    f'          v-for="doc in documents"{R}'
    f'          :key="doc.id"{R}'
    f'          @click="activeDocId = doc.id; loadDocument(doc)"{R}'
    f'          :class="[{R}'
    f"            'px-4 py-1.5 text-[13px] font-medium whitespace-nowrap rounded-lg transition-all duration-200',{R}"
    f'            activeDocId === doc.id{R}'
    f"              ? 'bg-white text-blue-700 shadow-[0_1px_3px_rgba(0,0,0,0.08)]'{R}"
    f"              : 'text-gray-500 hover:text-gray-700'{R}"
    f'          "]"{R}'
    f'        >{R}'
    f'          {{{{ doc.doc_name || doc.doc_type }}}}{R}'
    f'        </button>{R}'
    f'      </div>{R}'
    f'    </div>{R}'
    f'{R}'
    f'    <!-- 工具栏：去边框，改为极淡灰底通栏 -->{R}'
    f'    <div class="flex items-center justify-between px-4 py-2.5 bg-slate-50/80 rounded-xl mb-5">{R}'
    f'      <div class="flex items-center gap-2.5 text-[13px] text-gray-600">{R}'
    f'        <span v-if="metadata.patient_name" class="flex items-center gap-1 font-semibold text-gray-900">{R}'
    f'          <UserOutlined class="text-gray-400" /> {{{{ metadata.patient_name }}}}{R}'
    f'        </span>{R}'
    f'        <span v-if="metadata.department" class="w-px h-3 bg-gray-200"></span>{R}'
    f'        <span v-if="metadata.department" class="flex items-center gap-1">{R}'
    f'          <ApartmentOutlined class="text-gray-400" /> {{{{ metadata.department }}}}{R}'
    f'        </span>{R}'
    f'        <span v-if="metadata.doc_type" class="w-px h-3 bg-gray-200"></span>{R}'
    f'        <span v-if="metadata.doc_type" class="text-blue-500 font-medium font-mono text-[12px]">{R}'
    f'          {{{{ metadata.doc_type }}}}{R}'
    f'        </span>{R}'
    f'      </div>{R}'
    f'{R}'
    f'      <div class="flex items-center gap-2">{R}'
    f'        <span{R}'
    f'          v-if="annotations.length > 0"{R}'
    f'          :class="[{R}'
    f"            'px-2.5 py-1 text-[11px] font-bold rounded-full',{R}"
    f'            annotations.length > 3{R}'
    f"              ? 'bg-red-50 text-red-600'{R}"
    f"              : 'bg-orange-50 text-orange-600'{R}"
    f'          ]"{R}'
    f'        >{R}'
    f'          {{{{ annotations.length }}}} 个缺陷{R}'
    f'        </span>{R}'
    f'        <span v-else class="px-2.5 py-1 bg-emerald-50 text-emerald-600 text-[11px] font-bold rounded-full">无缺陷</span>{R}'
    f'      </div>{R}'
    f'    </div>{R}'
    f'{R}'
    f'    <!-- 加载中 -->{R}'
    f'    <div v-if="loading" class="flex items-center justify-center h-64">{R}'
    f'      <a-spin tip="正在加载文书内容..." />{R}'
    f'    </div>{R}'
    f'{R}'
    f'    <!-- 文书内容 -->{R}'
    f'    <div{R}'
    f'      v-else-if="renderedContent"{R}'
    f'      ref="contentRef"{R}'
    f'      class="emr-content prose prose-sm max-w-none p-6 bg-white rounded-xl border border-gray-100 shadow-[0_1px_4px_rgba(0,0,0,0.04)] overflow-auto"{R}'
    f'      :style="{{ maxHeight: maxHeight + \'px\' }}"{R}'
    f'      v-html="renderedContent"{R}'
    f'    />{R}'
)

# 组合：保留 line 1-3（index 0,1,2），插入新内容，然后从 line 57（index 56）开始接续
result = lines[:3] + [new_section] + lines[56:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(result)

print("EMRViewer template section patched successfully")
print(f"Total lines: {len(result)}")
