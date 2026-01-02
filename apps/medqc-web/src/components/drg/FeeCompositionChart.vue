<template>
  <div class="fee-composition-chart">
    <VChart :option="chartOption" :autoresize="true" style="height: 320px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent
} from 'echarts/components'
import type { FeeComposition } from '@/data/drg/mock-fee-monitoring'

use([
  CanvasRenderer,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent
])

interface Props {
  composition: FeeComposition
}

const props = defineProps<Props>()

const totalAmount = computed(() => {
  return Object.values(props.composition).reduce((a, b) => a + b, 0)
})

const chartOption = computed(() => {
  const data = [
    { value: props.composition.drugFee, name: '药品费' },
    { value: props.composition.materialFee, name: '材料费' },
    { value: props.composition.examFee, name: '检查费' },
    { value: props.composition.surgeryFee, name: '手术费' },
    { value: props.composition.treatmentFee, name: '治疗费' },
    { value: props.composition.bedFee, name: '床位费' },
    { value: props.composition.nursingFee, name: '护理费' },
    { value: props.composition.otherFee, name: '其他费用' }
  ].filter(item => item.value > 0)
   .sort((a, b) => b.value - a.value)

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      formatter: (params: any) => {
        return `
          <div style="font-weight:600;margin-bottom:4px;color:#1f1f1f">${params.name}</div>
          <div style="display:flex;justify-content:space-between;gap:16px;color:#595959">
            <span>金额</span>
            <span style="font-weight:600">¥${params.value.toLocaleString()}</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:16px;color:#595959">
            <span>占比</span>
            <span style="font-weight:600">${params.percent}%</span>
          </div>
        `
      }
    },
    title: {
      text: '总费用',
      subtext: `¥${(totalAmount.value / 1000).toFixed(1)}k`,
      left: '38%',
      top: '43%',
      textAlign: 'center',
      textStyle: {
        fontSize: 14,
        color: '#8c8c8c',
        fontWeight: 400
      },
      subtextStyle: {
        fontSize: 24,
        color: '#262626',
        fontWeight: 600,
        fontFamily: 'Din Alternate'
      }
    },
    legend: {
      orient: 'vertical',
      right: 20,
      top: 'middle',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        color: '#595959',
        rich: {
          name: {
            width: 60,
            fontSize: 12
          },
          value: {
            width: 70,
            align: 'right',
            color: '#262626',
            fontWeight: 500,
            fontFamily: 'Din Alternate'
          },
          percent: {
            width: 40,
            align: 'right',
            color: '#8c8c8c',
            fontSize: 12
          }
        }
      },
      formatter: (name: string) => {
        const item = data.find(d => d.name === name)
        const value = item ? item.value : 0
        const percent = ((value / totalAmount.value) * 100).toFixed(1) + '%'
        return `{name|${name}}{value|¥${(value/1000).toFixed(1)}k}{percent|${percent}}`
      }
    },
    series: [
      {
        name: '费用构成',
        type: 'pie',
        radius: ['55%', '75%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          scale: true,
          scaleSize: 10,
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.2)'
          }
        },
        data,
        color: [
          '#5B8FF9', // 强蓝
          '#5AD8A6', // 绿
          '#F6BD16', // 黄
          '#E8684A', // 红
          '#6DC8EC', // 浅蓝
          '#9270CA', // 紫
          '#FF9D4D', // 橙
          '#269A99'  // 青
        ]
      }
    ]
  }
})
</script>

<style scoped lang="scss">
.fee-composition-chart {
  width: 100%;
}
</style>
