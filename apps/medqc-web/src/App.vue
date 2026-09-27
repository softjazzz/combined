<script setup lang="ts">
import { ConfigProvider } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

// 认证初始化由路由守卫处理，不需要在这里调用
// 这样可以避免在访问demo页面等不需要认证的页面时触发403错误
dayjs.locale('zh-cn')

// antd 主题：品牌主色只在这里、tailwind.config.js 的 primary 和
// src/styles/index.css 的 --primary-color 三处声明，取值必须一致。
// 只收敛主色，不改变圆角/字号/间距等既有视觉参数。
const BRAND_PRIMARY = '#0a6cff'
const brandTheme = {
  token: {
    colorPrimary: BRAND_PRIMARY,
    colorLink: BRAND_PRIMARY,
  },
}
</script>

<template>
  <ConfigProvider
    :locale="zhCN"
    :theme="brandTheme"
  >
    <div id="app">
      <router-view />
    </div>
  </ConfigProvider>
</template>

<style>
#app {
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'SF Pro Display', 'San Francisco', 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  padding: 0;
  min-height: 100vh;
}
</style>
