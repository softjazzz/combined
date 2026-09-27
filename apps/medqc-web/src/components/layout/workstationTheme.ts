/**
 * 工作台（workstation-v5）专用的 antd 主题：v7.1 液态玻璃。
 * 只在 WorkstationLayout 内的嵌套 ConfigProvider 生效，不影响旧版后台页面。
 * 取值与 src/styles/tokens-v2.css 的 --mq-* 保持一致。
 */
import type { ThemeConfig } from 'ant-design-vue/es/config-provider/context'
import type { OverrideToken } from 'ant-design-vue/es/theme/interface'

const FONT_FAMILY =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Source Han Sans SC', " +
  "'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"

const components: Partial<OverrideToken> = {
  // 按钮统一为胶囊形
  Button: {
    borderRadius: 999,
    borderRadiusLG: 999,
    borderRadiusSM: 999,
    controlHeight: 36,
  },
  Modal: {
    borderRadiusLG: 26,
    colorBgMask: 'rgba(28, 38, 60, 0.26)',
    paddingContentHorizontalLG: 28,
  },
  Drawer: {
    borderRadiusLG: 26,
  },
  Card: {
    borderRadiusLG: 24,
  },
  // 表头浅灰底、弱分隔线，行悬浮用极浅品牌蓝
  Table: {
    borderRadiusLG: 18,
    colorFillAlter: 'rgba(118, 128, 160, 0.06)',
    colorBorderSecondary: 'rgba(0, 0, 0, 0.07)',
    controlItemBgHover: 'rgba(10, 108, 255, 0.04)',
  },
  Tag: {
    borderRadiusSM: 999,
  },
}

export const WORKSTATION_THEME: ThemeConfig = {
  token: {
    colorPrimary: '#0a6cff',
    colorLink: '#0a6cff',
    colorSuccess: '#34c759',
    colorWarning: '#ff9500',
    colorError: '#ff3b30',
    colorInfo: '#0a6cff',
    colorText: '#1d1d1f',
    colorTextSecondary: '#515154',
    colorTextTertiary: '#6e6e73',
    colorBorder: 'rgba(60, 60, 80, 0.14)',
    colorBorderSecondary: 'rgba(0, 0, 0, 0.07)',
    fontFamily: FONT_FAMILY,
    borderRadius: 12,
    borderRadiusLG: 18,
    borderRadiusSM: 8,
    controlHeight: 36,
    boxShadowSecondary: '0 12px 32px rgba(10, 55, 115, 0.14)',
  },
  // antd-vue 4.2.6 的 OverrideToken 把每个组件都声明为必填（映射类型缺少 ?），
  // 实际运行时只合并传入的组件，这里只覆盖用到的几个组件。
  components: components as OverrideToken,
  inherit: true,
}
