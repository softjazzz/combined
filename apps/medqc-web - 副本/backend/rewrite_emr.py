"""彻底重写 EMRViewer.vue 模板 1-68 行，使用干净 LF 换行"""

path = r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\components\qc\EMRViewer.vue'

# 读取原文件，保留第 68 行（空状态）之后的所有内容
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到 <!-- 空状态 --> 的位置，保留这里之后的内容
marker = '<!-- 空状态 -->'
pos = content.find(marker)
if pos == -1:
    print("ERROR: marker not found")
    exit(1)

tail = content[pos:]  # 从 <!-- 空状态 --> 起保留
print(f"Tail starts at byte: {pos}")
print(f"Tail preview: {repr(tail[:80])}")

# 新的模板头部（干净 LF）
new_head = '''<template>
  <div class="emr-viewer" ref="viewerRef">
    <!-- 文书标签页（胶囊 Pill 样式，与外层主 Tab 视觉层级区分） -->
    <div v-if="documents.length > 1" class="mb-5">
      <div class="inline-flex items-center gap-1 bg-gray-100/80 p-1 rounded-xl border border-gray-100/50">
        <button
          v-for="doc in documents"
          :key="doc.id"
          @click="activeDocId = doc.id; loadDocument(doc)"
          :class="[
            'px-4 py-1.5 text-[13px] font-medium whitespace-nowrap rounded-lg transition-all duration-200',
            activeDocId === doc.id
              ? 'bg-white text-blue-700 shadow-[0_1px_3px_rgba(0,0,0,0.08)]'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          {{ doc.doc_name || doc.doc_type }}
        </button>
      </div>
    </div>

    <!-- 工具栏：去边框，改为极淡灰底通栏 -->
    <div class="flex items-center justify-between px-4 py-2.5 bg-slate-50/80 rounded-xl mb-5">
      <div class="flex items-center gap-2.5 text-[13px] text-gray-600">
        <span v-if="metadata.patient_name" class="flex items-center gap-1 font-semibold text-gray-900">
          <UserOutlined class="text-gray-400" /> {{ metadata.patient_name }}
        </span>
        <span v-if="metadata.department" class="w-px h-3 bg-gray-200"></span>
        <span v-if="metadata.department" class="flex items-center gap-1">
          <ApartmentOutlined class="text-gray-400" /> {{ metadata.department }}
        </span>
        <span v-if="metadata.doc_type" class="w-px h-3 bg-gray-200"></span>
        <span v-if="metadata.doc_type" class="text-blue-500 font-medium font-mono text-[12px]">
          {{ metadata.doc_type }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <span
          v-if="annotations.length > 0"
          :class="[
            'px-2.5 py-1 text-[11px] font-bold rounded-full',
            annotations.length > 3
              ? 'bg-red-50 text-red-600'
              : 'bg-orange-50 text-orange-600'
          ]"
        >
          {{ annotations.length }} 个缺陷
        </span>
        <span v-else class="px-2.5 py-1 bg-emerald-50 text-emerald-600 text-[11px] font-bold rounded-full">无缺陷</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex items-center justify-center h-64">
      <a-spin tip="正在加载文书内容..." />
    </div>

    <!-- 文书内容 -->
    <div
      v-else-if="renderedContent"
      ref="contentRef"
      class="emr-content prose prose-sm max-w-none p-6 bg-white rounded-xl border border-gray-100 shadow-[0_1px_4px_rgba(0,0,0,0.04)] overflow-auto"
      :style="{ maxHeight: maxHeight + 'px' }"
      v-html="renderedContent"
    />

    '''

# 合并：新模板头 + 尾部原内容
new_content = new_head + tail

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)

# 验证
with open(path, 'r', encoding='utf-8') as f:
    verify = f.read()

has_double = '\r\r' in verify
print(f"Double CR: {'YES - ERROR' if has_double else 'NO - OK'}")
print(f"File written: {len(verify)} bytes")
print(f"Template starts OK: {verify[:50]}")
