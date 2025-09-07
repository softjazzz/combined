// 修复缺失的模型
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseKey)

async function fixMissingModels() {
  try {
    // 1. 获取阿里云提供商ID
    const { data: providers, error: providerError } = await supabase
      .from('llm_api_providers')
      .select('id')
      .eq('provider_code', 'alibaba')
      .single()

    if (providerError) {
      console.error('获取阿里云提供商失败:', providerError)
      return
    }

    console.log('阿里云提供商ID:', providers.id)

    // 2. 检查并添加缺失的模型
    const missingModels = [
      {
        model_code: 'qwen3-30b-a3b-instruct-2507',
        model_name: 'Qwen3-30B-A3B',
        description: '30B参数模型，高性能推理',
        context_length: 32768,
        pricing_tier: 'high',
        capabilities: ['高性能', '平衡推理', '多任务'],
        sort_order: 6
      },
      {
        model_code: 'qwen2.5-32b-instruct',
        model_name: 'Qwen2.5-32B-Instruct',
        description: '32B参数指令模型，高性能推理',
        context_length: 32768,
        pricing_tier: 'high',
        capabilities: ['大参数量', '高性能', '复杂推理'],
        sort_order: 7
      },
      {
        model_code: 'qwen2.5-14b-instruct',
        model_name: 'Qwen2.5-14B-Instruct',
        description: '14B参数指令模型，平衡性能与效率',
        context_length: 32768,
        pricing_tier: 'medium',
        capabilities: ['指令优化', '平衡性能', '多任务处理'],
        sort_order: 8
      }
    ]

    for (const modelConfig of missingModels) {
      // 检查模型是否已存在
      const { data: existingModel } = await supabase
        .from('llm_models')
        .select('id')
        .eq('model_code', modelConfig.model_code)
        .single()

      if (existingModel) {
        console.log(`模型 ${modelConfig.model_code} 已存在，跳过添加`)
        continue
      }

      // 添加新模型
      const { data: newModel, error: modelError } = await supabase
        .from('llm_models')
        .insert({
          provider_id: providers.id,
          model_code: modelConfig.model_code,
          model_name: modelConfig.model_name,
          description: modelConfig.description,
          context_length: modelConfig.context_length,
          pricing_tier: modelConfig.pricing_tier,
          capabilities: modelConfig.capabilities,
          parameters: {
            temperature: 0.7,
            max_tokens: 8192
          },
          is_default: false,
          is_active: true,
          sort_order: modelConfig.sort_order
        })
        .select()
        .single()

      if (modelError) {
        console.error(`添加模型 ${modelConfig.model_code} 失败:`, modelError)
        continue
      }

      console.log(`成功添加模型: ${newModel.model_code}`)
    }

    // 3. 验证最终结果
    const { data: allModels } = await supabase
      .from('llm_models')
      .select('*')
      .eq('provider_id', providers.id)
      .order('sort_order')

    console.log('\n=== 阿里云所有模型（最终版本）===')
    allModels?.forEach(model => {
      console.log(`- ${model.model_code}: ${model.model_name} (排序: ${model.sort_order})`)
    })

  } catch (error) {
    console.error('执行失败:', error)
  }
}

// 运行脚本
fixMissingModels()
