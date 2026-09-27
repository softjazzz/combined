/**
 * MedQC 定制图标库（v7.1 分层双色）
 * 规则：主体 16% 浅色填充 + 1.6 描边；细节 55% 透明；强调用白边实心徽章。viewBox 24。
 * 图标库画板（设计稿「图标库」）与此文件一一对应，新增图标先在设计稿确认。
 */

export type MqIconPart =
  | { kind: 'body'; d: string }
  | { kind: 'stroke'; d: string }
  | { kind: 'line'; d: string; opacity?: number }
  | { kind: 'solid'; d: string; opacity: number }
  | { kind: 'dot'; cx: number; cy: number; r: number }
  | { kind: 'badge'; mark: 'check' | 'plus' | 'bang' | 'question' }

const PAPER: MqIconPart[] = [
  { kind: 'body', d: 'M7 3h7l4 4v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z' },
  { kind: 'stroke', d: 'M14 3v4h4' },
  { kind: 'line', d: 'M8.5 10h6M8.5 13h4' },
]

const SHIELD = 'M12 3.2 5 6v5.6c0 4.4 3 7.6 7 9.2 4-1.6 7-4.8 7-9.2V6z'
const CIRCLE = 'M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17z'

export const MQ_ICONS = {
  overview: [
    { kind: 'body', d: 'M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z' },
    { kind: 'stroke', d: 'M10 20.5v-5h4v5' },
  ],
  pool: [
    { kind: 'line', d: 'M7 9V4.5h10V9' },
    { kind: 'line', d: 'M9.5 7h5' },
    {
      kind: 'body',
      d: 'M3.5 12h5.2l1.4 2.5h3.8l1.4-2.5h5.2v7a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19z',
    },
  ],
  running: [
    {
      kind: 'body',
      d: 'M5 4.5h14A1.5 1.5 0 0 1 20.5 6v9a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 15V6A1.5 1.5 0 0 1 5 4.5z',
    },
    { kind: 'stroke', d: 'M6.5 10.5h2.8l1.4-2.8 2.4 5.6 1.4-2.8h3' },
    { kind: 'line', d: 'M9 20h6M12 16.5V20' },
  ],
  final: [
    {
      kind: 'body',
      d: 'M3.5 7A1.5 1.5 0 0 1 5 5.5h4l2 2h8A1.5 1.5 0 0 1 20.5 9v9A1.5 1.5 0 0 1 19 19.5H5A1.5 1.5 0 0 1 3.5 18z',
    },
    { kind: 'badge', mark: 'check' },
  ],
  sample: [
    {
      kind: 'body',
      d: 'M9.5 3.5h5M10.5 3.5v5.2L5.6 17.4A2 2 0 0 0 7.4 20.5h9.2a2 2 0 0 0 1.8-3.1l-4.9-8.7V3.5',
    },
    { kind: 'line', d: 'M7.4 14.5h9.2' },
  ],
  fp_generate: [...PAPER, { kind: 'badge', mark: 'plus' }],
  fp_qc: [...PAPER, { kind: 'badge', mark: 'check' }],
  settlement: [
    { kind: 'body', d: 'M6 3.5h12v17l-2-1.3-2 1.3-2-1.3-2 1.3-2-1.3-2 1.3z' },
    { kind: 'line', d: 'M9 8h6M9 11h6M9 14h3.5' },
  ],
  rules: [
    { kind: 'body', d: SHIELD },
    { kind: 'stroke', d: 'm9 12 2.2 2.2L15.5 10' },
  ],
  custom_rule: [
    { kind: 'body', d: SHIELD },
    { kind: 'line', d: 'M12 8.5v6M9 11.5h6', opacity: 0.9 },
  ],
  surgery_catalog: [
    { kind: 'body', d: 'M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15H7.5A2.5 2.5 0 0 0 5 20.5z' },
    { kind: 'stroke', d: 'M5 20.5A2.5 2.5 0 0 1 7.5 18H19v2.5H7.5' },
    { kind: 'line', d: 'M9 7.5h6M9 10.5h4.5M9 13.5h3' },
  ],
  stats: [
    { kind: 'body', d: 'M5 13h3v7H5zM10.5 8h3v12h-3zM16 4h3v16h-3z' },
    { kind: 'line', d: 'M3.5 20.5h17' },
  ],
  drg: [
    { kind: 'body', d: 'M12 3.5a8.5 8.5 0 1 0 8.5 8.5H12z' },
    { kind: 'solid', d: 'M14.5 2.2A8.5 8.5 0 0 1 21.8 9.5h-7.3z', opacity: 0.55 },
  ],
  icd: [
    { kind: 'body', d: 'M10.5 3.5a7 7 0 1 1 0 14 7 7 0 0 1 0-14z' },
    { kind: 'stroke', d: 'm15.6 15.6 4.9 4.9' },
    { kind: 'line', d: 'M8.6 8.5 7 10.5l1.6 2M12.4 8.5l1.6 2-1.6 2', opacity: 0.8 },
  ],
  upload: [
    { kind: 'body', d: 'M7 18.5a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 9a4.75 4.75 0 0 1-.5 9.5z' },
    { kind: 'stroke', d: 'M12 16v-6M9.5 12.2 12 9.7l2.5 2.5' },
  ],
  download: [
    { kind: 'body', d: 'M7 18.5a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 9a4.75 4.75 0 0 1-.5 9.5z' },
    { kind: 'stroke', d: 'M12 10v6M9.5 13.8 12 16.3l2.5-2.5' },
  ],
  data: [
    {
      kind: 'body',
      d: 'M4.5 6c0-1.7 3.4-3 7.5-3s7.5 1.3 7.5 3v12c0 1.7-3.4 3-7.5 3s-7.5-1.3-7.5-3z',
    },
    { kind: 'line', d: 'M4.5 6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3' },
  ],
  settings: [
    {
      kind: 'body',
      d: 'M18.79 10.31 L21.19 10.55 L21.19 13.45 L18.79 13.69 L18.00 15.61 L19.52 17.47 L17.47 19.52 L15.61 18.00 L13.69 18.79 L13.45 21.19 L10.55 21.19 L10.31 18.79 L8.39 18.00 L6.53 19.52 L4.48 17.47 L6.00 15.61 L5.21 13.69 L2.81 13.45 L2.81 10.55 L5.21 10.31 L6.00 8.39 L4.48 6.53 L6.53 4.48 L8.39 6.00 L10.31 5.21 L10.55 2.81 L13.45 2.81 L13.69 5.21 L15.61 6.00 L17.47 4.48 L19.52 6.53 L18.00 8.39z',
    },
    { kind: 'stroke', d: 'M12 9.2a2.8 2.8 0 1 1 0 5.6 2.8 2.8 0 0 1 0-5.6z' },
  ],
  sync: [
    { kind: 'body', d: CIRCLE },
    {
      kind: 'stroke',
      d: 'M8.2 10.4a4.2 4.2 0 0 1 7.4-1.2M15.8 13.6a4.2 4.2 0 0 1-7.4 1.2M15.6 6.8v2.4h-2.4M8.4 17.2v-2.4h2.4',
    },
  ],
  task: [
    { kind: 'body', d: 'M12 5.5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15z' },
    { kind: 'stroke', d: 'M12 9.5V13l2.2 1.4M10 2.8h4M18.6 6.4l1.4-1.4' },
  ],
  tech_error: [
    { kind: 'body', d: 'M10.3 4.2a2 2 0 0 1 3.4 0l7.2 12.6a2 2 0 0 1-1.7 3H4.8a2 2 0 0 1-1.7-3z' },
    { kind: 'stroke', d: 'M12 9.5v4' },
    { kind: 'dot', cx: 12, cy: 16.6, r: 0.95 },
  ],
  success: [
    { kind: 'body', d: CIRCLE },
    { kind: 'stroke', d: 'm8.4 12.2 2.4 2.4 4.8-5' },
  ],
  doc: [...PAPER],
  issue: [...PAPER, { kind: 'badge', mark: 'bang' }],
  data_gap: [...PAPER, { kind: 'badge', mark: 'question' }],
  stack: [
    { kind: 'line', d: 'M9.5 2.5h6.5l3.5 3.5v10a1.8 1.8 0 0 1-1.8 1.8', opacity: 0.45 },
    { kind: 'body', d: 'M6.5 5.5h7l4 4v10a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2z' },
    { kind: 'stroke', d: 'M13.5 5.5v4h4' },
    { kind: 'line', d: 'M7.5 13h7M7.5 16h4.5' },
  ],
} satisfies Record<string, MqIconPart[]>

export type MqIconName = keyof typeof MQ_ICONS

/** 图标底座色调：中性 / 品牌 / 语义色（语义色只用于数据状态） */
export const MQ_ICON_TONES = {
  neutral: { color: '#4A5468', rgb: '74,84,104' },
  brand: { color: '#0A6CFF', rgb: '10,108,255' },
  success: { color: '#1E9E47', rgb: '52,199,89' },
  warning: { color: '#C25E00', rgb: '255,149,0' },
  danger: { color: '#E0263A', rgb: '255,59,48' },
} as const

export type MqIconTone = keyof typeof MQ_ICON_TONES
