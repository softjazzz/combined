// 测试UI实际显示的内容
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
  
  // 映射非标准类别到标准类别
  const categoryStr = String(category || '').toLowerCase();
  const mappings = {
    'medical_order': 'progress_note',
    'nursing_document': 'progress_note',
    'blood_transfusion': 'progress_note',
    'emergency_record': 'progress_note',
    '输血记录': 'progress_note',
    '医嘱记录': 'progress_note',
    '护理记录': 'progress_note',
    '急诊记录': 'progress_note'
  };

  const mappedCategory = mappings[categoryStr];
  if (mappedCategory && DOCUMENT_CATEGORY_CONFIG[mappedCategory]) {
    return DOCUMENT_CATEGORY_CONFIG[mappedCategory];
  }

  // 最后的fallback - 返回"未分类"而不是英文代码
  return {
    label: '未分类',
    description: '未识别的文书类别',
    color: '#666666',
    icon: 'FileOutlined',
    sortOrder: 999
  };
}

async function testUIDisplay() {
  console.log('=== 测试UI实际显示内容 ===\n');

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

    console.log('1. 模拟表格单元格显示内容:');
    console.log('   (这是用户在UI中实际看到的内容)\n');

    rules.forEach((rule, index) => {
      if (index < 8) { // 显示前8条
        const primary = rule.primary_document_category;
        const displayConfig = getDocumentCategoryDisplayConfig(primary);
        
        console.log(`   规则 ${rule.rule_code}:`);
        console.log(`     数据库存储值: "${primary}"`);
        console.log(`     UI显示标签: "${displayConfig.label}"`);
        console.log(`     标签颜色: ${displayConfig.color}`);
        console.log('');
      }
    });

    // 2. 测试筛选器选项
    console.log('2. 模拟筛选器下拉选项:');
    console.log('   (这是用户在筛选器中看到的选项)\n');
    
    const uniqueCategories = [...new Set(rules.map(r => r.primary_document_category))];
    uniqueCategories.forEach(category => {
      const config = getDocumentCategoryDisplayConfig(category);
      console.log(`   选项: "${config.label}" (值: ${category})`);
    });

    // 3. 验证是否有任何情况会显示英文代码
    console.log('\n3. 检查是否有情况会显示英文代码:');
    const testCases = ['progress_note', 'invalid_category', null, undefined, '输血记录', 'emergency_record'];
    
    testCases.forEach(testCase => {
      const config = getDocumentCategoryDisplayConfig(testCase);
      const wouldShowEnglish = config.label === testCase;
      console.log(`   输入: "${testCase}" -> 显示: "${config.label}" ${wouldShowEnglish ? '❌ 显示英文!' : '✅ 显示中文'}`);
    });

  } catch (error) {
    console.error('❌ 测试过程中发生错误:', error.message);
  }
}

testUIDisplay();
