import { createClient } from '@supabase/supabase-js';

const supabase = createClient('https://afsbjvihjfsngobccnjx.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg');

// 模拟前端API调用
async function testFrontendAPIs() {
  console.log('测试前端API调用...\n');
  
  try {
    // 1. 测试统计概览
    console.log('1. 测试统计概览API...');
    const { data: allRecords, error: recordsError } = await supabase
      .from('medical_records')
      .select('id, status, qc_score, created_at');
    
    if (recordsError) {
      console.error('获取记录失败:', recordsError);
      return;
    }
    
    console.log('✅ 获取到记录数:', allRecords.length);
    
    // 计算统计数据
    const totalRecords = allRecords.length;
    const pendingRecords = allRecords.filter(r => r.status === 'pending').length;
    const analyzingRecords = allRecords.filter(r => r.status === 'analyzing').length;
    const completedRecords = allRecords.filter(r => r.status === 'completed').length;
    
    const completedWithScores = allRecords.filter(r => r.status === 'completed' && r.qc_score !== null);
    const averageScore = completedWithScores.length > 0 
      ? completedWithScores.reduce((sum, r) => sum + (r.qc_score || 0), 0) / completedWithScores.length
      : 0;
    
    const passRate = completedWithScores.length > 0
      ? (completedWithScores.filter(r => (r.qc_score || 0) >= 80).length / completedWithScores.length) * 100
      : 0;
    
    console.log('统计概览:');
    console.log(`  总记录数: ${totalRecords}`);
    console.log(`  待分析: ${pendingRecords}`);
    console.log(`  分析中: ${analyzingRecords}`);
    console.log(`  已完成: ${completedRecords}`);
    console.log(`  平均分: ${averageScore.toFixed(1)}`);
    console.log(`  通过率: ${passRate.toFixed(1)}%`);
    
    // 2. 测试趋势数据
    console.log('\n2. 测试趋势数据...');
    const now = new Date();
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    const trendData = [];
    for (let i = 0; i < 30; i++) {
      const date = new Date(thirtyDaysAgo.getTime() + i * 24 * 60 * 60 * 1000);
      const dateStr = date.toISOString().split('T')[0];
      
      const dayRecords = allRecords.filter(record => {
        const recordDate = new Date(record.created_at).toISOString().split('T')[0];
        return recordDate === dateStr;
      });
      
      if (dayRecords.length > 0) {
        const dayCompleted = dayRecords.filter(r => r.status === 'completed' && r.qc_score !== null);
        const dayAvgScore = dayCompleted.length > 0 
          ? dayCompleted.reduce((sum, r) => sum + (r.qc_score || 0), 0) / dayCompleted.length
          : 0;
        
        trendData.push({
          period: dateStr,
          recordCount: dayRecords.length,
          averageScore: dayAvgScore,
          passRate: dayCompleted.length > 0 
            ? (dayCompleted.filter(r => (r.qc_score || 0) >= 80).length / dayCompleted.length) * 100
            : 0
        });
      }
    }
    
    console.log('✅ 趋势数据点数:', trendData.length);
    if (trendData.length > 0) {
      console.log('最近5天趋势:');
      trendData.slice(-5).forEach(item => {
        console.log(`  ${item.period}: ${item.recordCount}条记录, 平均分: ${item.averageScore.toFixed(1)}, 通过率: ${item.passRate.toFixed(1)}%`);
      });
    }
    
    // 3. 测试部门统计
    console.log('\n3. 测试部门统计...');
    const deptStats = {};
    allRecords.forEach(record => {
      const dept = record.department || '未知';
      if (!deptStats[dept]) {
        deptStats[dept] = { 
          department: dept,
          records: [],
          recordCount: 0,
          totalScore: 0,
          passCount: 0
        };
      }
      deptStats[dept].records.push(record);
      deptStats[dept].recordCount++;
      
      if (record.status === 'completed' && record.qc_score !== null) {
        deptStats[dept].totalScore += record.qc_score;
        if (record.qc_score >= 80) {
          deptStats[dept].passCount++;
        }
      }
    });
    
    const departmentStats = Object.values(deptStats).map(dept => {
      const completedRecords = dept.records.filter(r => r.status === 'completed' && r.qc_score !== null);
      return {
        department: dept.department,
        recordCount: dept.recordCount,
        averageScore: completedRecords.length > 0 
          ? dept.totalScore / completedRecords.length
          : 0,
        passRate: completedRecords.length > 0 
          ? (dept.passCount / completedRecords.length) * 100
          : 0,
        color: '#1890ff'
      };
    });
    
    console.log('✅ 部门统计:');
    departmentStats.forEach(dept => {
      console.log(`  ${dept.department}: ${dept.recordCount}条记录, 平均分: ${dept.averageScore.toFixed(1)}, 通过率: ${dept.passRate.toFixed(1)}%`);
    });
    
    // 4. 测试评分分布
    console.log('\n4. 测试评分分布...');
    const scoreRanges = [
      { range: '90-100', min: 90, max: 100, count: 0 },
      { range: '80-89', min: 80, max: 89, count: 0 },
      { range: '70-79', min: 70, max: 79, count: 0 },
      { range: '60-69', min: 60, max: 69, count: 0 },
      { range: '0-59', min: 0, max: 59, count: 0 }
    ];
    
    const scoredRecords = allRecords.filter(r => r.qc_score !== null);
    scoredRecords.forEach(record => {
      const score = record.qc_score;
      for (const range of scoreRanges) {
        if (score >= range.min && score <= range.max) {
          range.count++;
          break;
        }
      }
    });
    
    const scoreDistribution = scoreRanges.map(range => ({
      scoreRange: range.range,
      count: range.count,
      percentage: scoredRecords.length > 0 ? (range.count / scoredRecords.length) * 100 : 0
    }));
    
    console.log('✅ 评分分布:');
    scoreDistribution.forEach(item => {
      console.log(`  ${item.scoreRange}分: ${item.count}条 (${item.percentage.toFixed(1)}%)`);
    });
    
    console.log('\n🎉 所有API测试完成！');
    
  } catch (error) {
    console.error('❌ API测试失败:', error);
  }
}

testFrontendAPIs(); 