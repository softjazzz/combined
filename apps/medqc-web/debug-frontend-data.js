// 调试前端数据处理逻辑
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

// 模拟前端的DOCUMENT_CATEGORY_CONFIG
const DOCUMENT_CATEGORY_CONFIG = {
  'progress_note': {
    label: '病程记录',
    description: '住院期间的病情变化、治疗过程、医嘱执行等动态记录',
    color: '#1890ff',
    icon: 'FileTextOutlined',
    sortOrder: 2
  },
  'admission_record': {
    label: '入院记录',
    description: '患者入院时的基本信息、主诉、现病史、既往史、体格检查等记录',
    color: '#52c41a',
    icon: 'LoginOutlined',
    sortOrder: 1
  },
  'discharge_record': {
    label: '出院记录',
    description: '患者出院时的诊疗总结、出院诊断、治疗效果等记录',
    color: '#faad14',
    icon: 'LogoutOutlined',
    sortOrder: 3
  },
  'operation_record': {
    label: '手术相关记录',
    description: '手术记录、麻醉记录、术前讨论、术后总结等手术相关文书',
    color: '#f5222d',
    icon: 'MedicineBoxOutlined',
    sortOrder: 4
  },
  'examination_report': {
    label: '辅助检查',
    description: '影像学检查、实验室检查、病理检查等辅助检查报告',
    color: '#722ed1',
    icon: 'ExperimentOutlined',
    sortOrder: 5
  },
  'consent_form': {
    label: '知情同意书',
    description: '各类医疗操作的知情同意书、风险告知书等',
    color: '#13c2c2',
    icon: 'SafetyCertificateOutlined',
    sortOrder: 6
  }
};

// 模拟前端的getDocumentCategoryDisplayConfig函数
function getDocumentCategoryDisplayConfig(category) {
  const config = DOCUMENT_CATEGORY_CONFIG[category];
  if (config) {
    return config;
  }
  
  // Fallback逻辑
  return {
    label: category, // 这里就是问题所在！
    description: '',
    color: '#666666',
    icon: 'FileOutlined',
    sortOrder: 999
  };
}

async function debugFrontendData() {
  console.log('=== 调试前端数据处理逻辑 ===\n');

  try {
    // 1. 获取规则数据
    const { data: rules, error } = await supabase
      .from('qc_rules')
      .select('*')
      .limit(10);

    if (error) {
      console.error('❌ 获取规则失败:', error.message);
      return;
    }

    console.log('1. 测试getDocumentCategoryDisplayConfig函数:');
    const testCategories = ['progress_note', 'admission_record', 'invalid_category', null, undefined];
    
    testCategories.forEach(category => {
      const result = getDocumentCategoryDisplayConfig(category);
      console.log(`   "${category}" -> label: "${result.label}"`);
    });

    console.log('\n2. 分析实际规则数据:');
    rules.forEach((rule, index) => {
      if (index < 5) { // 只显示前5条
        const primary = rule.primary_document_category;
        const config = getDocumentCategoryDisplayConfig(primary);
        
        console.log(`   规则 ${rule.rule_code}:`);
        console.log(`     primary_document_category: "${primary}"`);
        console.log(`     显示标签: "${config.label}"`);
        console.log(`     是否在DOCUMENT_CATEGORY_CONFIG中: ${!!DOCUMENT_CATEGORY_CONFIG[primary]}`);
      }
    });

    // 3. 检查是否有不在标准配置中的类别
    console.log('\n3. 检查非标准类别:');
    const allPrimaryCategories = new Set();
    rules.forEach(rule => {
      if (rule.primary_document_category) {
        allPrimaryCategories.add(rule.primary_document_category);
      }
    });

    const standardCategories = new Set(Object.keys(DOCUMENT_CATEGORY_CONFIG));
    const nonStandardCategories = [...allPrimaryCategories].filter(cat => !standardCategories.has(cat));
    
    if (nonStandardCategories.length > 0) {
      console.log('   ❌ 发现非标准类别:', nonStandardCategories);
      nonStandardCategories.forEach(cat => {
        const config = getDocumentCategoryDisplayConfig(cat);
        console.log(`     "${cat}" -> 显示为: "${config.label}"`);
      });
    } else {
      console.log('   ✅ 所有类别都是标准类别');
    }

  } catch (error) {
    console.error('❌ 调试过程中发生错误:', error.message);
  }
}

debugFrontendData();
