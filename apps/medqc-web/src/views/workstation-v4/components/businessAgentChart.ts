// 助手图表的几何计算：只把后端给出的原值映射到坐标，不改写、不推算数值。
import type { BusinessAgentChart } from '@/api/businessAgent'

export const LINE_VIEW = { width: 520, height: 190, left: 40, right: 24, top: 28, bottom: 36 }

export interface LinePoint {
  label: string
  value: number | null
  x: number
  y: number | null
}

export interface LineGeometry {
  points: LinePoint[]
  segments: string[]
  areas: string[]
  grid: { value: number; y: number }[]
}

// 纵轴上限取不小于最大值的整齐数（5 的倍数起步），仅用于刻度。
export function axisMax(values: number[]): number {
  const max = Math.max(0, ...values)
  if (max <= 5) return 5
  const step = max <= 20 ? 5 : max <= 100 ? 10 : 50
  return Math.ceil(max / step) * step
}

export function numericCount(chart: BusinessAgentChart): number {
  return chart.points.filter((point) => point.value !== null).length
}

export function buildLine(chart: BusinessAgentChart): LineGeometry {
  const { width, height, left, right, top, bottom } = LINE_VIEW
  const plotBottom = height - bottom
  const max = axisMax(chart.points.flatMap((point) => (point.value === null ? [] : [point.value])))
  const count = chart.points.length
  const x = (index: number) =>
    count === 1 ? (left + width - right) / 2 : left + (index * (width - right - left)) / (count - 1)
  const y = (value: number) => plotBottom - (value / max) * (plotBottom - top)
  const points: LinePoint[] = chart.points.map((point, index) => ({
    label: point.label,
    value: point.value,
    x: x(index),
    y: point.value === null ? null : y(point.value),
  }))
  // 缺失值处断开折线，不连接也不补零。
  const groups: LinePoint[][] = []
  let current: LinePoint[] = []
  for (const point of points) {
    if (point.y === null) {
      if (current.length) groups.push(current)
      current = []
    } else current.push(point)
  }
  if (current.length) groups.push(current)
  const format = (point: LinePoint) => `${point.x.toFixed(1)},${(point.y as number).toFixed(1)}`
  const segments = groups
    .filter((group) => group.length > 1)
    .map((group) => group.map(format).join(' '))
  const areas = groups
    .filter((group) => group.length > 1)
    .map(
      (group) =>
        `${group[0].x.toFixed(1)},${plotBottom} ${group.map(format).join(' ')} ${group[group.length - 1].x.toFixed(1)},${plotBottom}`,
    )
  const grid = [0, max / 2, max].map((value) => ({ value, y: y(value) }))
  return { points, segments, areas, grid }
}

export function chartLabel(chart: BusinessAgentChart): string {
  const body = chart.points
    .map((point) => `${point.label}${point.value === null ? '无数据' : point.value}`)
    .join('，')
  return `${chart.metric}${chart.type === 'line' ? '折线图' : '条形图'}：${body}`
}
