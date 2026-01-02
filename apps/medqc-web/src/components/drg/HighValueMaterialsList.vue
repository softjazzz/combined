<template>
  <div class="high-value-materials-list">
    <a-empty v-if="materials.length === 0" description="暂无高值耗材" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
    
    <div v-else class="materials-grid">
      <div v-for="item in materials" :key="item.id" class="material-card">
        <div class="card-header">
          <div class="icon-wrapper">
             <MedicineBoxOutlined v-if="item.category.includes('器械') || item.category === '骨科植入物'" />
             <HeartOutlined v-else-if="item.category.includes('心脏')" />
             <ExperimentOutlined v-else />
          </div>
          <div class="header-info">
            <div class="material-name" :title="item.name">{{ item.name }}</div>
            <div class="material-category">{{ item.category }}</div>
          </div>
          <a-tag :color="item.inCatalog ? 'success' : 'warning'" class="status-tag">
            {{ item.inCatalog ? '医保' : '自费' }}
          </a-tag>
        </div>
        
        <div class="card-body">
          <div class="info-row">
            <span class="label">使用日期</span>
            <span class="value">{{ formatDate(item.usedDate) }}</span>
          </div>
          <div class="info-row">
            <span class="label">单价 × 数量</span>
            <span class="value">¥{{ item.unitPrice.toLocaleString() }} × {{ item.quantity }}</span>
          </div>
          <div class="divider"></div>
          <div class="total-row">
            <span class="label">小计</span>
            <span class="total-value">¥{{ item.totalPrice.toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="materials.length > 0" class="materials-summary">
      <div class="summary-card">
        <span class="summary-label">高值耗材总计</span>
        <span class="summary-value">¥{{ totalPrice.toLocaleString() }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Empty } from 'ant-design-vue'
import { MedicineBoxOutlined, HeartOutlined, ExperimentOutlined } from '@ant-design/icons-vue'
import type { HighValueMaterial } from '@/data/drg/mock-fee-monitoring'

interface Props {
  materials: HighValueMaterial[]
}

const props = defineProps<Props>()

const totalPrice = computed(() => {
  return props.materials.reduce((sum, item) => sum + item.totalPrice, 0)
})

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}
</script>

<style scoped lang="scss">
.high-value-materials-list {
  .materials-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  
  .material-card {
    background: #fff;
    border: 1px solid #f0f0f0;
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s ease;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
      border-color: #e6f7ff;
    }
    
    .card-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
      
      .icon-wrapper {
        width: 36px;
        height: 36px;
        background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #1890ff;
        font-size: 18px;
        flex-shrink: 0;
      }
      
      .header-info {
        flex: 1;
        min-width: 0;
        
        .material-name {
          font-weight: 600;
          font-size: 14px;
          color: #1f1f1f;
          margin-bottom: 2px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        
        .material-category {
          font-size: 12px;
          color: #8c8c8c;
        }
      }
      
      .status-tag {
        margin: 0;
        border-radius: 4px;
        font-size: 10px; // 更小的字体
        line-height: index;
      }
    }
    
    .card-body {
      .info-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-size: 12px;
        
        .label {
          color: #8c8c8c;
        }
        .value {
          color: #595959;
          font-weight: 500;
        }
      }
      
      .divider {
        height: 1px;
        background: #f5f5f5;
        margin: 12px 0;
      }
      
      .total-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .label {
          font-size: 12px;
          color: #8c8c8c;
        }
        
        .total-value {
          color: #1890ff;
          font-weight: 700;
          font-size: 16px;
          font-family: 'Din Alternate', -apple-system, BlinkMacSystemFont, sans-serif;
        }
      }
    }
  }
  
  .materials-summary {
    display: flex;
    justify-content: flex-end;
    
    .summary-card {
      background: linear-gradient(135deg, #f0f5ff 0%, #f6ffed 100%); // 混合渐变
      padding: 12px 24px;
      border-radius: 8px;
      display: flex;
      align-items: baseline;
      gap: 12px;
      border: 1px solid #d9d9d9;
      
      .summary-label {
        color: #595959;
        font-size: 14px;
      }
      
      .summary-value {
        color: #cf1322; // 红色突出金额
        font-size: 20px;
        font-weight: 700;
        font-family: 'Din Alternate', sans-serif;
      }
    }
  }
}
</style>
