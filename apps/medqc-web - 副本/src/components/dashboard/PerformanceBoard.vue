<template>
  <div class="perf-board">
    <div class="board-header">
      <h3 class="board-title">
        <TrophyOutlined class="title-icon" />
        工作表现
      </h3>
      <a-segmented
        v-model:value="activePeriod"
        :options="periodOptions"
        size="small"
        @change="handlePeriodChange"
      />
    </div>

    <div class="board-content">
      <!-- 缺陷排名 -->
      <div class="ranking-section">
        <div class="section-title">
          <BugOutlined /> 缺陷发现排名
        </div>
        <div
          v-if="rankingData.defect_ranking?.length"
          class="ranking-list"
        >
          <div
            v-for="(item, index) in rankingData.defect_ranking.slice(0, 5)"
            :key="'d-' + index"
            class="ranking-item"
          >
            <span :class="['rank-badge', `rank-${index + 1}`]">{{ index + 1 }}</span>
            <span class="rank-name">{{ item.user_name || item.name }}</span>
            <div class="rank-bar-container">
              <div
                class="rank-bar"
                :style="{ width: getBarWidth(item.count || item.value, rankingData.defect_ranking) + '%' }"
              />
            </div>
            <span class="rank-value">{{ item.count || item.value }}</span>
          </div>
        </div>
        <div
          v-else
          class="empty-ranking"
        >
          <span class="text-gray-400 text-xs">暂无数据</span>
        </div>
      </div>

      <!-- 病历排名 -->
      <div class="ranking-section">
        <div class="section-title">
          <FileTextOutlined /> 病历审核排名
        </div>
        <div
          v-if="rankingData.record_ranking?.length"
          class="ranking-list"
        >
          <div
            v-for="(item, index) in rankingData.record_ranking.slice(0, 5)"
            :key="'r-' + index"
            class="ranking-item"
          >
            <span :class="['rank-badge', `rank-${index + 1}`]">{{ index + 1 }}</span>
            <span class="rank-name">{{ item.user_name || item.name }}</span>
            <div class="rank-bar-container">
              <div
                class="rank-bar rank-bar-green"
                :style="{ width: getBarWidth(item.count || item.value, rankingData.record_ranking) + '%' }"
              />
            </div>
            <span class="rank-value">{{ item.count || item.value }}</span>
          </div>
        </div>
        <div
          v-else
          class="empty-ranking"
        >
          <span class="text-gray-400 text-xs">暂无数据</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { TrophyOutlined, BugOutlined, FileTextOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  rankingData: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'period-change', period: string): void
}>()

const activePeriod = ref('本周')
const periodOptions = ['本周', '本月']

const handlePeriodChange = (val: string) => {
  const periodMap: Record<string, string> = {
    '本周': 'this_week',
    '本月': 'this_month',
  }
  emit('period-change', periodMap[val] || 'this_week')
}

const getBarWidth = (value: number, list: any[]) => {
  if (!list?.length) return 0
  const max = Math.max(...list.map(i => i.count || i.value || 0))
  return max > 0 ? (value / max) * 100 : 0
}
</script>

<style scoped>
.perf-board {
  background: white;
  border-radius: 16px;
  border: 1px solid #f0f0f0;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  height: 100%;
}
.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.board-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}
.title-icon { color: #faad14; }

.board-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ranking-section {}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.rank-badge {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #999;
  background: #f5f5f5;
  flex-shrink: 0;
}
.rank-1 { background: linear-gradient(135deg, #ffd700, #ffaa00); color: white; }
.rank-2 { background: linear-gradient(135deg, #c0c0c0, #a0a0a0); color: white; }
.rank-3 { background: linear-gradient(135deg, #cd7f32, #b87333); color: white; }

.rank-name {
  width: 56px;
  flex-shrink: 0;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-bar-container {
  flex: 1;
  height: 6px;
  background: #f5f5f5;
  border-radius: 3px;
  overflow: hidden;
}
.rank-bar {
  height: 100%;
  background: linear-gradient(90deg, #1677ff, #4096ff);
  border-radius: 3px;
  transition: width 0.6s ease;
}
.rank-bar-green {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.rank-value {
  width: 28px;
  text-align: right;
  font-weight: 700;
  color: #333;
  flex-shrink: 0;
}

.empty-ranking {
  padding: 16px;
  text-align: center;
  background: #fafafa;
  border-radius: 8px;
}
</style>
