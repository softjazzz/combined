// 添加 Qwen2.5-7B-1M 模型到数据库
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseKey)

async function addQwenModels() {
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

    // 2. 定义要添加的新模型
    const newModels = [
      {
        model_code: 'qwen-flash-2025-07-28',
        model_name: 'Qwen Flash (2025-07-28)',
        description: '最新Flash版本，极速响应',
        context_length: 8192,
        pricing_tier: 'low',
        capabilities: ['极速响应', '最新版本', '高效处理'],
        sort_order: 10
      },
      {
        model_code: 'qwen3-4b',
        model_name: 'Qwen3-4B',
        description: '轻量级Qwen3模型，快速高效',
        context_length: 32768,
        pricing_tier: 'low',
        capabilities: ['轻量级', '快速响应', '成本友好'],
        sort_order: 11
      },
      {
        model_code: 'qwen3-8b',
        model_name: 'Qwen3-8B',
        description: '中等规模Qwen3模型，性能均衡',
        context_length: 32768,
        pricing_tier: 'medium',
        capabilities: ['性能均衡', '多场景适用', '稳定可靠'],
        sort_order: 12
      },
      {
        model_code: 'qwen3-14b',
        model_name: 'Qwen3-14B',
        description: '大规模Qwen3模型，强大性能',
        context_length: 32768,
        pricing_tier: 'high',
        capabilities: ['大规模参数', '强大性能', '专业任务'],
        sort_order: 13
      }
    ]

    // 3. 批量添加新模型
    for (const modelConfig of newModels) {
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

    // 4. 修改现有模型的显示名称
    const { error: updateError } = await supabase
      .from('llm_models')
      .update({ model_name: 'Qwen3-30B-A3B' })
      .eq('model_code', 'qwen3-30b-a3b-instruct-2507')

    if (updateError) {
      console.error('更新Qwen3-30B显示名称失败:', updateError)
    } else {
      console.log('成功更新Qwen3-30B显示名称为Qwen3-30B-A3B')
    }

    // 5. 验证最终结果
    const { data: allModels } = await supabase
      .from('llm_models')
      .select('*')
      .eq('provider_id', providers.id)
      .order('sort_order')

    console.log('\n=== 阿里云所有模型 ===')
    allModels?.forEach(model => {
      console.log(`- ${model.model_code}: ${model.model_name} (排序: ${model.sort_order})`)
    })

  } catch (error) {
    console.error('执行失败:', error)
  }
}

// 运行脚本
addQwenModels()
