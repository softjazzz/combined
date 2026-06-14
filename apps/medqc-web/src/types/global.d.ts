// 全局类型声明
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

export {}

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $router: Router
    $route: RouteLocationNormalizedLoaded
  }
}

declare global {
  // 任何类型，用于临时解决类型问题
  type AnyType = any

  // 常用的数组类型
  type AnyArray = any[]
  type StringArray = string[]
  type NumberArray = number[]

  // 常用的对象类型
  type AnyObject = Record<string, any>
  type StringObject = Record<string, string>

  // 函数类型
  type AnyFunction = (...args: any[]) => any
  type VoidFunction = () => void

  // 事件处理器类型
  type EventHandler = (event: any) => void
  type ChangeHandler = (value: any) => void

  // API响应类型
  interface ApiResponse<T = any> {
    success: boolean
    data?: T
    error?: string
    message?: string
  }

  // 分页类型
  interface PaginationData<T = any> {
    data: T[]
    total: number
    page: number
    pageSize: number
  }
}
