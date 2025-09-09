<template>
  <div class="min-h-screen bg-gray-50">
    <div class="container mx-auto px-4 py-8">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-4">智慧医保质控系统</h1>
        <p class="text-xl text-gray-600">欢迎使用医保智能审核平台</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
          <div class="flex items-center mb-4">
            <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <span class="text-2xl">📋</span>
            </div>
            <h3 class="text-lg font-semibold ml-4">规则管理</h3>
          </div>
          <p class="text-gray-600 mb-4">管理医保质控规则，支持批量导入和编辑</p>
          <a-button type="primary" @click="goToRules">进入管理</a-button>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
          <div class="flex items-center mb-4">
            <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <span class="text-2xl">🧪</span>
            </div>
            <h3 class="text-lg font-semibold ml-4">沙箱测试</h3>
          </div>
          <p class="text-gray-600 mb-4">测试规则逻辑，验证审核效果</p>
          <a-button @click="goToSandbox">开始测试</a-button>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
          <div class="flex items-center mb-4">
            <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <span class="text-2xl">📊</span>
            </div>
            <h3 class="text-lg font-semibold ml-4">数据统计</h3>
          </div>
          <p class="text-gray-600 mb-4">查看系统运行数据和统计报告</p>
          <a-button @click="goToDashboard">查看数据</a-button>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-md p-6">
        <h2 class="text-2xl font-bold mb-4">快速开始</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 class="text-lg font-semibold mb-2">1. 导入规则</h3>
            <p class="text-gray-600 mb-4">首次使用请先导入医保质控规则</p>
            <a-button type="primary" @click="goToImport">导入规则</a-button>
          </div>
          <div>
            <h3 class="text-lg font-semibold mb-2">2. 测试验证</h3>
            <p class="text-gray-600 mb-4">使用沙箱功能测试规则效果</p>
            <a-button @click="goToSandbox">测试规则</a-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goToRules() {
  router.push('/rules')
}

function goToSandbox() {
  router.push('/sandbox')
}

function goToDashboard() {
  router.push('/dashboard')
}

function goToImport() {
  router.push('/rules/import')
}
</script>


