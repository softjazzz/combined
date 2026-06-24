<template>
  <div class="table-skeleton">
    <div class="skeleton-header">
      <a-row :gutter="16">
        <a-col
          v-for="col in columns"
          :key="col"
          :span="24 / columns"
        >
          <a-skeleton-button
            active
            size="small"
            style="width: 80%"
          />
        </a-col>
      </a-row>
    </div>
    <div
      v-for="i in rows"
      :key="i"
      class="skeleton-row"
    >
      <a-row
        :gutter="16"
        align="middle"
      >
        <a-col
          v-for="col in columns"
          :key="col"
          :span="24 / columns"
        >
          <a-skeleton
            active
            :title="false"
            :paragraph="{ rows: 1, width: '90%' }"
          />
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  rows: {
    type: Number,
    default: 5
  },
  columns: {
    type: Number,
    default: 4
  }
})
</script>

<style scoped lang="scss">
.table-skeleton {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  
  .skeleton-header {
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #f0f0f0;
  }
  
  .skeleton-row {
    margin-bottom: 24px;
    
    &:last-child {
      margin-bottom: 0;
    }
  }
}
</style>
