import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabase = createClient(
  process.env.VITE_SUPABASE_URL,
  process.env.VITE_SUPABASE_ANON_KEY
);

async function debugCategoryData() {
  console.log('=== 调试文书类别数据 ===\n');

  try {
    // 1. 检查document_category_config表
    console.log('1. 检查document_category_config表:');
    const { data: configs, error: configError } = await supabase
      .from('document_category_config')
      .select('*')
      .order('sort_order');
    
    if (configError) {
      console.error('❌ 配置表查询失败:', configError);
    } else {
      console.log(`✅ 找到${configs.length}条配置:`);
      configs.forEach(config => {
        console.log(`  - ${config.category_code}: "${config.category_name}" (排序: ${config.sort_order})`);
      });
    }

    // 2. 检查qc_rules表中的primary_document_category
    console.log('\n2. 检查qc_rules表中的primary_document_category:');
    const { data: rules, error: rulesError } = await supabase
      .from('qc_rules')
      .select('primary_document_category')
      .not('primary_document_category', 'is', null);
    
    if (rulesError) {
      console.error('❌ 规则表查询失败:', rulesError);
    } else {
      // 统计primary_document_category的值
      const stats = {};
      rules.forEach(rule => {
        const category = rule.primary_document_category;
        if (category) {
          stats[category] = (stats[category] || 0) + 1;
        }
      });
      
      console.log(`✅ 找到${rules.length}条规则记录:`);
      console.log('   primary_document_category统计:');
      Object.entries(stats).forEach(([category, count]) => {
        console.log(`     "${category}": ${count}条`);
      });
    }

    // 3. 检查document_categories字段
    console.log('\n3. 检查document_categories字段:');
    const { data: rulesWithCategories, error: categoriesError } = await supabase
      .from('qc_rules')
      .select('document_categories')
      .not('document_categories', 'is', null);
    
    if (categoriesError) {
      console.error('❌ 文档类别字段查询失败:', categoriesError);
    } else {
      const allCategories = new Set();
      rulesWithCategories.forEach(rule => {
        if (rule.document_categories && Array.isArray(rule.document_categories)) {
          rule.document_categories.forEach(cat => allCategories.add(cat));
        }
      });
      
      console.log(`✅ document_categories字段中的所有值:`);
      Array.from(allCategories).sort().forEach(category => {
        console.log(`     "${category}"`);
      });
    }

    // 4. 模拟前端的标准化处理
    console.log('\n4. 模拟前端标准化处理:');
    const CANONICAL_CATEGORIES = new Set([
      'admission_record', 'progress_note', 'discharge_record', 
      'operation_record', 'examination_report', 'consent_form'
    ]);

    const CATEGORY_MAPPING = {
      'nursing_document': 'progress_note',
      'medical_order': 'progress_note', 
      'blood_transfusion': 'progress_note',
      'emergency_record': 'progress_note',
      'consultation_record': 'progress_note',
      'surgery_record': 'operation_record',
      'lab_report': 'examination_report',
      'imaging_report': 'examination_report',
      'pathology_report': 'examination_report'
    };

    console.log('   标准类别集合:', Array.from(CANONICAL_CATEGORIES));
    console.log('   类别映射规则:', CATEGORY_MAPPING);

    // 应用映射到统计数据
    const normalizedStats = {};
    if (rules && rules.length > 0) {
      // 重新计算stats
      const currentStats = {};
      rules.forEach(rule => {
        const category = rule.primary_document_category;
        if (category) {
          currentStats[category] = (currentStats[category] || 0) + 1;
        }
      });

      Object.entries(currentStats).forEach(([category, count]) => {
      let normalizedCategory = category;
      
      if (!CANONICAL_CATEGORIES.has(category)) {
        normalizedCategory = CATEGORY_MAPPING[category];
        console.log(`   映射: "${category}" -> "${normalizedCategory}"`);
      }
      
        if (normalizedCategory && CANONICAL_CATEGORIES.has(normalizedCategory)) {
          normalizedStats[normalizedCategory] = (normalizedStats[normalizedCategory] || 0) + count;
        } else {
          console.log(`   ⚠️  忽略非标准类别: "${category}"`);
        }
      });
    }

    console.log('\n   标准化后的统计:');
    Object.entries(normalizedStats).forEach(([category, count]) => {
      console.log(`     "${category}": ${count}条`);
    });

  } catch (error) {
    console.error('❌ 调试过程中发生错误:', error);
  }
}

debugCategoryData();
