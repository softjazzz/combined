<script setup lang="ts">
import { ConfigProvider } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

// 认证初始化由路由守卫处理，不需要在这里调用
// 这样可以避免在访问demo页面等不需要认证的页面时触发403错误
dayjs.locale('zh-cn')
</script>

<template>
  <ConfigProvider :locale="zhCN">
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
