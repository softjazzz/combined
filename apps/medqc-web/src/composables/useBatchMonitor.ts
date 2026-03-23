import { ref, computed } from 'vue'
import { supabase, TABLES } from '@/lib/supabase'
import { message } from 'ant-design-vue'

// 批量任务接口
interface BatchTask {
  id: string
  user_id: string
  task_type: 'upload' | 'analysis' | 'export'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  total_items: number
  processed_items: number
  failed_items: number
  progress_percentage: number
  error_details?: Record<string, unknown>
  metadata?: Record<string, unknown>
  created_at: string
  started_at?: string
  completed_at?: string
}

// 任务统计接口
interface TaskStatistics {
  totalTasks: number
  activeTasks: number
  completedTasks: number
  failedTasks: number
  totalItems: number
  processedItems: number
  successRate: number
}

type TaskChangePayload = {
  eventType: 'INSERT' | 'UPDATE' | 'DELETE'
  new: BatchTask | null
  old: BatchTask | null
}

export function useBatchMonitor() {
  // 响应式数据
  const allTasks = ref<BatchTask[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const subscription = ref<unknown>(null)
  type RealtimeSubscription = { unsubscribe: () => void }

  // 计算属性
  const activeTasks = computed(() =>
    allTasks.value.filter((task) => task.status === 'pending' || task.status === 'processing'),
  )

  const recentTasks = computed(() =>
    allTasks.value
      .filter((task) => task.status === 'completed' || task.status === 'failed')
      .sort((a, b) => new Date(b.completed_at!).getTime() - new Date(a.completed_at!).getTime())
      .slice(0, 10),
  )

  const taskStatistics = computed((): TaskStatistics => {
    const tasks = allTasks.value
    const totalTasks = tasks.length
    const activeTasks = tasks.filter(
      (t) => t.status === 'pending' || t.status === 'processing',
    ).length
    const completedTasks = tasks.filter((t) => t.status === 'completed').length
    const failedTasks = tasks.filter((t) => t.status === 'failed').length
    const totalItems = tasks.reduce((sum, t) => sum + t.total_items, 0)
    const processedItems = tasks.reduce((sum, t) => sum + t.processed_items, 0)
    const successRate =
      totalItems > 0
        ? ((processedItems - tasks.reduce((sum, t) => sum + t.failed_items, 0)) / totalItems) * 100
        : 0

    return {
      totalTasks,
      activeTasks,
      completedTasks,
      failedTasks,
      totalItems,
      processedItems,
      successRate: Math.round(successRate * 100) / 100,
    }
  })

  /**
   * 获取用户的批量任务
   */
  const fetchTasks = async (limit = 50) => {
    isLoading.value = true
    error.value = null

    try {
      const { data: userData } = await supabase.auth.getUser()
      if (!userData.user) {
        throw new Error('用户未登录')
      }

      const { data, error: fetchError } = await supabase
        .from(TABLES.BATCH_PROCESSING_TASKS)
        .select('*')
        .eq('user_id', userData.user.id)
        .order('created_at', { ascending: false })
        .limit(limit)

      if (fetchError) {
        throw new Error(`获取任务失败: ${fetchError.message}`)
      }

      allTasks.value = data || []
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取任务失败'
      error.value = errorMessage
      console.error('获取批量任务失败:', err)
      message.error(errorMessage)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 刷新任务列表
   */
  const refreshTasks = async () => {
    await fetchTasks()
  }

  /**
   * 订阅任务状态变化
   */
  const subscribeToTasks = () => {
    if (subscription.value) {
      ;(subscription.value as RealtimeSubscription).unsubscribe()
    }

    subscription.value = supabase
      .channel('batch_tasks_monitor')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: TABLES.BATCH_PROCESSING_TASKS,
        },
        (payload: unknown) => {
          handleTaskChange(payload as TaskChangePayload)
        },
      )
      .subscribe()

    return subscription.value
  }

  /**
   * 处理任务变化
   */
  const handleTaskChange = (payload: TaskChangePayload) => {
    const { eventType, new: newRecord, old: oldRecord } = payload

    switch (eventType) {
      case 'INSERT':
        if (newRecord) {
          // 检查是否是当前用户的任务
          const currentUserId = supabase.auth
            .getUser()
            .then(({ data }: { data: { user: { id: string } | null } }) => data.user?.id)
          currentUserId.then((userId) => {
            if (newRecord.user_id === userId) {
              allTasks.value.unshift(newRecord)
            }
          })
        }
        break

      case 'UPDATE':
        if (newRecord) {
          const index = allTasks.value.findIndex((task) => task.id === newRecord.id)
          if (index !== -1) {
            allTasks.value[index] = newRecord

            // 如果任务完成，显示通知
            if (oldRecord?.status !== 'completed' && newRecord.status === 'completed') {
              message.success(`任务"${getTaskName(newRecord.task_type)}"已完成`)
            } else if (oldRecord?.status !== 'failed' && newRecord.status === 'failed') {
              message.error(`任务"${getTaskName(newRecord.task_type)}"执行失败`)
            }
          }
        }
        break

      case 'DELETE':
        if (oldRecord) {
          const index = allTasks.value.findIndex((task) => task.id === oldRecord.id)
          if (index !== -1) {
            allTasks.value.splice(index, 1)
          }
        }
        break
    }
  }

  /**
   * 取消任务
   */
  const cancelTask = async (taskId: string) => {
    try {
      const { error: updateError } = await supabase
        .from(TABLES.BATCH_PROCESSING_TASKS)
        .update({
          status: 'failed',
          error_details: { message: '用户取消任务' },
          completed_at: new Date().toISOString(),
        })
        .eq('id', taskId)

      if (updateError) {
        throw new Error(`取消任务失败: ${updateError.message}`)
      }

      message.success('任务已取消')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '取消任务失败'
      console.error('取消任务失败:', err)
      message.error(errorMessage)
      throw err
    }
  }

  /**
   * 重试任务
   */
  const retryTask = async (taskId: string) => {
    try {
      const { error: updateError } = await supabase
        .from(TABLES.BATCH_PROCESSING_TASKS)
        .update({
          status: 'pending',
          processed_items: 0,
          failed_items: 0,
          progress_percentage: 0,
          error_details: null,
          started_at: null,
          completed_at: null,
        })
        .eq('id', taskId)

      if (updateError) {
        throw new Error(`重试任务失败: ${updateError.message}`)
      }

      message.success('任务已重新启动')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '重试任务失败'
      console.error('重试任务失败:', err)
      message.error(errorMessage)
      throw err
    }
  }

  /**
   * 删除任务
   */
  const deleteTask = async (taskId: string) => {
    try {
      const { error: deleteError } = await supabase
        .from(TABLES.BATCH_PROCESSING_TASKS)
        .delete()
        .eq('id', taskId)

      if (deleteError) {
        throw new Error(`删除任务失败: ${deleteError.message}`)
      }

      message.success('任务已删除')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '删除任务失败'
      console.error('删除任务失败:', err)
      message.error(errorMessage)
      throw err
    }
  }

  /**
   * 获取任务详情
   */
  const getTaskById = (taskId: string): BatchTask | undefined => {
    return allTasks.value.find((task) => task.id === taskId)
  }

  /**
   * 清理已完成的任务
   */
  const cleanupCompletedTasks = async (daysToKeep = 7) => {
    try {
      const cutoffDate = new Date()
      cutoffDate.setDate(cutoffDate.getDate() - daysToKeep)

      const { error: deleteError } = await supabase
        .from(TABLES.BATCH_PROCESSING_TASKS)
        .delete()
        .in('status', ['completed', 'failed'])
        .lt('completed_at', cutoffDate.toISOString())

      if (deleteError) {
        throw new Error(`清理任务失败: ${deleteError.message}`)
      }

      // 刷新任务列表
      await refreshTasks()
      message.success('已清理过期任务')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '清理任务失败'
      console.error('清理任务失败:', err)
      message.error(errorMessage)
      throw err
    }
  }

  /**
   * 获取任务类型显示名称
   */
  const getTaskName = (taskType: string): string => {
    const names = {
      upload: '批量上传',
      analysis: '批量分析',
      export: '批量导出',
    }
    return names[taskType as keyof typeof names] || '未知任务'
  }

  /**
   * 获取任务状态显示名称
   */
  const getStatusName = (status: string): string => {
    const names = {
      pending: '等待中',
      processing: '处理中',
      completed: '已完成',
      failed: '失败',
    }
    return names[status as keyof typeof names] || status
  }

  /**
   * 取消订阅
   */
  const unsubscribe = () => {
    if (subscription.value) {
      ;(subscription.value as RealtimeSubscription).unsubscribe()
      subscription.value = null
    }
  }

  return {
    // 响应式数据
    allTasks,
    activeTasks,
    recentTasks,
    taskStatistics,
    isLoading,
    error,

    // 方法
    fetchTasks,
    refreshTasks,
    subscribeToTasks,
    unsubscribe,
    cancelTask,
    retryTask,
    deleteTask,
    getTaskById,
    cleanupCompletedTasks,
    getTaskName,
    getStatusName,
  }
}
