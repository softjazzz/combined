// 检查Supabase数据库中的文书类别数据
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Supabase配置缺失');
  console.log('VITE_SUPABASE_URL:', supabaseUrl ? '已设置' : '未设置');
  console.log('VITE_SUPABASE_ANON_KEY:', supabaseKey ? '已设置' : '未设置');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function checkDatabaseData() {
  console.log('=== 检查Supabase数据库中的文书类别数据 ===\n');

  try {
    // 1. 检查document_category_config表
    console.log('1. 检查document_category_config表:');
    const { data: categoryConfig, error: configError } = await supabase
      .from('document_category_config')
      .select('*')
      .order('sort_order');

    if (configError) {
      console.error('❌ 查询document_category_config失败:', configError.message);
    } else {
      console.log(`✅ 找到${categoryConfig.length}条文书类别配置:`);
      categoryConfig.forEach(config => {
        console.log(`  - ${config.category_code}: "${config.category_name}" (排序: ${config.sort_order})`);
      });
    }

    // 2. 检查qc_rules表中的primary_document_category字段
    console.log('\n2. 检查qc_rules表中的primary_document_category字段:');
    const { data: rules, error: rulesError } = await supabase
      .from('qc_rules')
      .select('id, rule_code, name, primary_document_category, document_categories')
      .limit(20);

    if (rulesError) {
      console.error('❌ 查询qc_rules失败:', rulesError.message);
    } else {
      console.log(`✅ 找到${rules.length}条规则记录 (前20条):`);
      
      // 统计primary_document_category的值
      const primaryStats = {};
      rules.forEach(rule => {
        const primary = rule.primary_document_category;
        if (primary) {
          primaryStats[primary] = (primaryStats[primary] || 0) + 1;
        }
      });

      console.log('\n   primary_document_category统计:');
      Object.entries(primaryStats).forEach(([value, count]) => {
        console.log(`     "${value}": ${count}条`);
      });

      // 显示前5条规则的详细信息
      console.log('\n   前5条规则详情:');
      rules.slice(0, 5).forEach(rule => {
        console.log(`     ${rule.rule_code}: "${rule.name}"`);
        console.log(`       primary: "${rule.primary_document_category}"`);
        console.log(`       categories: ${JSON.stringify(rule.document_categories)}`);
      });
    }

    // 3. 检查document_categories字段中的值
    console.log('\n3. 检查document_categories字段中的所有值:');
    const { data: allRules, error: allRulesError } = await supabase
      .from('qc_rules')
      .select('document_categories');

    if (allRulesError) {
      console.error('❌ 查询所有规则失败:', allRulesError.message);
    } else {
      const categoryStats = {};
      allRules.forEach(rule => {
        if (rule.document_categories && Array.isArray(rule.document_categories)) {
          rule.document_categories.forEach(cat => {
            categoryStats[cat] = (categoryStats[cat] || 0) + 1;
          });
        }
      });

      console.log('   document_categories中的所有值统计:');
      Object.entries(categoryStats)
        .sort(([,a], [,b]) => b - a)
        .forEach(([value, count]) => {
          console.log(`     "${value}": ${count}次`);
        });
    }

  } catch (error) {
    console.error('❌ 检查数据库时发生错误:', error.message);
  }
}

checkDatabaseData();
