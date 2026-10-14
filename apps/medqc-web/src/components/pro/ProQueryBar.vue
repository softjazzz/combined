<template>
  <div
    class="pro-query-bar px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4"
  >
    <div class="pro-query-bar__filters flex items-center gap-3 flex-1 min-w-0">
      <slot name="filters" />
    </div>
    <div class="pro-query-bar__actions flex items-center gap-3">
      <slot name="actions" />
    </div>
  </div>
  <div
    v-if="$slots.hint"
    class="px-6 py-2 text-xs text-blue-700 bg-blue-50/70 border-b border-blue-100"
  >
    <slot name="hint" />
  </div>
</template>
