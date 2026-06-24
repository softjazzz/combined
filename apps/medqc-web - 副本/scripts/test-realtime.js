import { config } from 'dotenv'
import { createClient } from '@supabase/supabase-js'

// 加载环境变量
config()

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY

console.log('🧪 测试实时功能...\n')

async function testRealtimeFeatures() {
  try {
    const supabase = createClient(supabaseUrl, supabaseKey)
    
    console.log('1️⃣ 测试数据库连接...')
    const { data, error } = await supabase
      .from('medical_records')
      .select('id')
      .limit(1)
    
    if (error) {
      throw error
    }
    
    console.log('✅ 数据库连接成功')
    
    console.log('\n2️⃣ 测试实时订阅...')
    
    // 创建实时订阅
    const channel = supabase
      .channel('test-medical-records')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'medical_records'
        },
        (payload) => {
          console.log('📋 收到医疗记录变化:', payload.eventType)
          console.log('   新记录:', payload.new?.patient_name || 'N/A')
          console.log('   旧记录:', payload.old?.patient_name || 'N/A')
        }
      )
      .subscribe((status) => {
        console.log(`📡 订阅状态: ${status}`)
        if (status === 'SUBSCRIBED') {
          console.log('✅ 实时订阅成功建立')
          
          // 3秒后创建一条测试记录
          setTimeout(async () => {
            console.log('\n3️⃣ 创建测试记录触发实时更新...')
            
            const { data: newRecord, error: insertError } = await supabase
              .from('medical_records')
              .insert({
                patient_name: '实时测试患者',
                patient_age: 30,
                patient_gender: 'M',
                department: '测试科室',
                admission_date: '2024-01-15',
                record_type: 'inpatient',
                content: '这是一条实时测试记录',
                status: 'pending'
              })
              .select()
              .single()
            
            if (insertError) {
              console.error('❌ 创建测试记录失败:', insertError)
            } else {
              console.log('✅ 测试记录创建成功:', newRecord.id)
              
              // 2秒后更新记录状态
              setTimeout(async () => {
                console.log('\n4️⃣ 更新记录状态...')
                
                const { error: updateError } = await supabase
                  .from('medical_records')
                  .update({ status: 'analyzing' })
                  .eq('id', newRecord.id)
                
                if (updateError) {
                  console.error('❌ 更新记录失败:', updateError)
                } else {
                  console.log('✅ 记录状态更新成功')
                  
                  // 2秒后删除测试记录
                  setTimeout(async () => {
                    console.log('\n5️⃣ 清理测试记录...')
                    
                    const { error: deleteError } = await supabase
                      .from('medical_records')
                      .delete()
                      .eq('id', newRecord.id)
                    
                    if (deleteError) {
                      console.error('❌ 删除记录失败:', deleteError)
                    } else {
                      console.log('✅ 测试记录清理完成')
                    }
                    
                    // 测试完成，取消订阅
                    setTimeout(() => {
                      console.log('\n📡 取消订阅...')
                      supabase.removeChannel(channel)
                      console.log('🎉 实时功能测试完成！')
                      process.exit(0)
                    }, 1000)
                  }, 2000)
                }
              }, 2000)
            }
          }, 3000)
        }
      })
    
    // 10秒后超时
    setTimeout(() => {
      console.log('\n⏰ 测试超时')
      supabase.removeChannel(channel)
      process.exit(1)
    }, 15000)
    
  } catch (error) {
    console.error('❌ 测试失败:', error.message)
    process.exit(1)
  }
}

async function main() {
  console.log('配置信息:')
  console.log(`- Supabase URL: ${supabaseUrl}`)
  console.log(`- 测试时间: ${new Date().toLocaleString()}`)
  console.log()
  
  await testRealtimeFeatures()
}

main().catch(console.error) 