/**
 * 控制台测试工具
 * 直接在浏览器控制台中使用
 */

import { supabase } from '@/lib/backend-store'

// 测试表访问权限
async function testBatchTable() {
  try {
    console.log('🔍 测试批量处理任务表访问...')

    const { data: user } = await supabase.auth.getUser()
    if (!user.user) {
      console.error('❌ 用户未登录')
      return false
    }

    console.log('👤 当前用户ID:', user.user.id)

    // 测试查询所有记录
    console.log('📊 查询所有批量任务...')
    const { data: allTasks, error: allError } = await supabase
      .from('batch_processing_tasks')
      .select('*')

    if (allError) {
      console.error('❌ 查询所有任务失败:', allError)
    } else {
      console.log('✅ 查询所有任务成功:', allTasks)
    }

    // 测试查询用户任务
    console.log('👤 查询用户任务...')
    const { data: userTasks, error: userError } = await supabase
      .from('batch_processing_tasks')
      .select('*')
      .eq('user_id', user.user.id)

    if (userError) {
      console.error('❌ 查询用户任务失败:', userError)
    } else {
      console.log('✅ 查询用户任务成功:', userTasks)
    }

    // 测试插入新任务
    console.log('➕ 测试插入新任务...')
    const { data: newTask, error: insertError } = await supabase
      .from('batch_processing_tasks')
      .insert({
        user_id: user.user.id,
        task_type: 'upload',
        total_items: 1,
        status: 'pending',
      })
      .select()
      .single()

    if (insertError) {
      console.error('❌ 插入任务失败:', insertError)
    } else {
      console.log('✅ 插入任务成功:', newTask)
    }

    return true
  } catch (error) {
    console.error('❌ 测试失败:', error)
    return false
  }
}

// 测试批量上传功能
async function testBatchUpload() {
  try {
    console.log('🚀 测试批量上传功能...')

    // 创建测试文件
    const testContent = `患者姓名：测试患者
性别：男
年龄：30
科室：测试科室
入院时间：2024-12-20
主诉：测试主诉`

    const testFile = new File([testContent], '测试病案.txt', { type: 'text/plain' })

    console.log('📁 创建测试文件:', testFile)

    // 这里可以测试文件处理逻辑
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      console.log('📄 文件内容:', content)
    }
    reader.readAsText(testFile)

    return true
  } catch (error) {
    console.error('❌ 测试批量上传失败:', error)
    return false
  }
}

// 检查批量监控组件状态
async function checkBatchMonitor() {
  try {
    console.log('📊 检查批量监控组件状态...')

    // 查找批量监控组件
    const monitorElement = document.querySelector('.batch-progress-monitor')
    if (monitorElement) {
      console.log('✅ 找到批量监控组件:', monitorElement)
    } else {
      console.log('⚠️ 未找到批量监控组件')
    }

    // 查找批量上传组件
    const uploadElement = document.querySelector('.batch-upload-container')
    if (uploadElement) {
      console.log('✅ 找到批量上传组件:', uploadElement)
    } else {
      console.log('⚠️ 未找到批量上传组件')
    }

    return true
  } catch (error) {
    console.error('❌ 检查组件失败:', error)
    return false
  }
}

// 暴露到全局对象
if (typeof window !== 'undefined') {
  ;(window as any).testBatchTable = testBatchTable
  ;(window as any).testBatchUpload = testBatchUpload
  ;(window as any).checkBatchMonitor = checkBatchMonitor

  console.log('🧪 控制台测试工具已加载')
  console.log('📝 可用命令：')
  console.log('   testBatchTable() - 测试批量任务表')
  console.log('   testBatchUpload() - 测试批量上传功能')
  console.log('   checkBatchMonitor() - 检查批量监控组件')
}
