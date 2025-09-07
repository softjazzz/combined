import { createClient } from '@supabase/supabase-js';

const supabase = createClient('https://afsbjvihjfsngobccnjx.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg');

console.log('测试统计API数据获取...');

async function testStats() {
  try {
    console.log('1. 测试medical_records总数...');
    const { data: records, error: recordsError } = await supabase
      .from('medical_records')
      .select('*');
    
    if (recordsError) {
      console.error('获取records失败:', recordsError);
      return;
    }
    
    console.log('Records总数:', records.length);
    
    // 按科室统计
    const deptStats = {};
    records.forEach(record => {
      const dept = record.department || '未知';
      if (!deptStats[dept]) {
        deptStats[dept] = { count: 0, totalScore: 0, scores: [] };
      }
      deptStats[dept].count++;
      if (record.qc_score) {
        deptStats[dept].totalScore += record.qc_score;
        deptStats[dept].scores.push(record.qc_score);
      }
    });
    
    console.log('\n2. 部门统计:');
    Object.keys(deptStats).forEach(dept => {
      const stat = deptStats[dept];
      const avgScore = stat.scores.length > 0 ? (stat.totalScore / stat.scores.length).toFixed(1) : 0;
      console.log(`  ${dept}: ${stat.count}条记录, 平均分: ${avgScore}`);
    });
    
    // 评分分布
    const scoreRanges = { '90-100': 0, '80-89': 0, '70-79': 0, '60-69': 0, '0-59': 0 };
    records.forEach(record => {
      const score = record.qc_score;
      if (score >= 90) scoreRanges['90-100']++;
      else if (score >= 80) scoreRanges['80-89']++;
      else if (score >= 70) scoreRanges['70-79']++;
      else if (score >= 60) scoreRanges['60-69']++;
      else scoreRanges['0-59']++;
    });
    
    console.log('\n3. 评分分布:');
    Object.keys(scoreRanges).forEach(range => {
      console.log(`  ${range}分: ${scoreRanges[range]}条`);
    });
    
    // 测试趋势数据
    console.log('\n4. 测试趋势数据...');
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    const trendData = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(sevenDaysAgo.getTime() + i * 24 * 60 * 60 * 1000);
      const dateStr = date.toISOString().split('T')[0];
      
      const dayRecords = records.filter(record => {
        const recordDate = new Date(record.created_at).toISOString().split('T')[0];
        return recordDate === dateStr;
      });
      
      trendData.push({
        date: dateStr,
        count: dayRecords.length,
        avgScore: dayRecords.length > 0 ? 
          (dayRecords.reduce((sum, r) => sum + (r.qc_score || 0), 0) / dayRecords.length).toFixed(1) : 0
      });
    }
    
    console.log('趋势数据:');
    trendData.forEach(item => {
      console.log(`  ${item.date}: ${item.count}条记录, 平均分: ${item.avgScore}`);
    });
    
  } catch (error) {
    console.error('测试失败:', error);
  }
}

testStats(); 