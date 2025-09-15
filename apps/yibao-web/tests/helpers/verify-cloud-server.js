#!/usr/bin/env node

/**
 * 验证云服务器环境下的测试病历数据集成
 */

const API_BASE_URL = 'http://43.163.116.243:8002';
const FRONTEND_BASE_URL = 'http://43.163.116.243:3008';

async function login() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: 'admin@yibao.com',
                password: 'admin123'
            })
        });

        if (response.ok) {
            const data = await response.json();
            console.log('✅ 云服务器登录成功');
            return data.access_token;
        } else {
            throw new Error(`登录失败: ${response.status}`);
        }
    } catch (error) {
        console.error('❌ 登录失败:', error.message);
        return null;
    }
}

async function testMedicalRecordsAPI(token) {
    try {
        console.log('\n🧪 测试云服务器病历API...');
        const response = await fetch(`${API_BASE_URL}/api/medical-records?page=1&page_size=10`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            console.log(`✅ 病历API正常 - 返回 ${data.data.length} 条记录，总计 ${data.total} 条`);
            
            // 显示前3条记录
            console.log('\n📋 前3条病历记录:');
            data.data.slice(0, 3).forEach((record, index) => {
                console.log(`  ${index + 1}. ${record.name} - ${record.patient_name} (${record.gender}, ${record.age}岁)`);
                console.log(`     科室: ${record.department} | 风险: ${record.violation_risk} | 场景: ${record.test_scenario}`);
            });
            
            return true;
        } else {
            console.error(`❌ 病历API失败: ${response.status}`);
            return false;
        }
    } catch (error) {
        console.error('❌ 病历API错误:', error.message);
        return false;
    }
}

async function testFrontendPages() {
    try {
        console.log('\n🌐 测试云服务器前端页面...');
        
        // 测试主页
        const mainPageResponse = await fetch(FRONTEND_BASE_URL);
        if (mainPageResponse.ok) {
            console.log('✅ 主应用页面正常');
        } else {
            console.log(`❌ 主应用页面异常: ${mainPageResponse.status}`);
        }
        
        // 测试病历展示页面
        const testPageResponse = await fetch(`${FRONTEND_BASE_URL}/test-medical-records.html`);
        if (testPageResponse.ok) {
            console.log('✅ 测试病历展示页面正常');
        } else {
            console.log(`❌ 测试病历展示页面异常: ${testPageResponse.status}`);
        }
        
        // 测试验证页面
        const verifyPageResponse = await fetch(`${FRONTEND_BASE_URL}/test-page-verification.html`);
        if (verifyPageResponse.ok) {
            console.log('✅ 验证工具页面正常');
        } else {
            console.log(`❌ 验证工具页面异常: ${verifyPageResponse.status}`);
        }
        
        return true;
    } catch (error) {
        console.error('❌ 前端页面测试错误:', error.message);
        return false;
    }
}

async function testStatisticsAPI(token) {
    try {
        console.log('\n📊 测试统计数据API...');
        const response = await fetch(`${API_BASE_URL}/api/medical-records/statistics/overview`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const stats = await response.json();
            console.log('✅ 统计数据API正常');
            console.log('\n📈 数据统计概览:');
            console.log(`  总病历数: ${stats.total_records}`);
            console.log(`  风险分布: 拦截${stats.risk_distribution.block} | 警告${stats.risk_distribution.warn} | 信息${stats.risk_distribution.info} | 通过${stats.risk_distribution.pass}`);
            console.log(`  年龄分布: 儿童${stats.age_distribution.儿童} | 成年${stats.age_distribution.成年} | 老年${stats.age_distribution.老年}`);
            console.log(`  性别分布: 男${stats.gender_distribution.男} | 女${stats.gender_distribution.女}`);
            
            return true;
        } else {
            console.error(`❌ 统计数据API失败: ${response.status}`);
            return false;
        }
    } catch (error) {
        console.error('❌ 统计数据API错误:', error.message);
        return false;
    }
}

async function main() {
    console.log('🚀 开始验证云服务器环境下的Yibao测试病历数据...\n');
    console.log(`🌐 前端地址: ${FRONTEND_BASE_URL}`);
    console.log(`🔗 后端地址: ${API_BASE_URL}\n`);
    
    // 1. 测试登录
    const token = await login();
    if (!token) {
        console.log('\n❌ 验证失败: 无法获取认证token');
        return;
    }
    
    // 2. 测试API
    const apiTest1 = await testMedicalRecordsAPI(token);
    const apiTest2 = await testStatisticsAPI(token);
    
    // 3. 测试前端页面
    const frontendTest = await testFrontendPages();
    
    // 4. 总结
    console.log('\n' + '='.repeat(60));
    console.log('📋 云服务器验证结果总结:');
    console.log(`  认证系统: ${token ? '✅ 正常' : '❌ 异常'}`);
    console.log(`  病历列表API: ${apiTest1 ? '✅ 正常' : '❌ 异常'}`);
    console.log(`  统计数据API: ${apiTest2 ? '✅ 正常' : '❌ 异常'}`);
    console.log(`  前端页面: ${frontendTest ? '✅ 正常' : '❌ 异常'}`);
    
    const allPassed = token && apiTest1 && apiTest2 && frontendTest;
    console.log(`\n🎯 整体状态: ${allPassed ? '✅ 全部正常' : '❌ 存在问题'}`);
    
    if (allPassed) {
        console.log('\n🎉 恭喜！云服务器环境测试病历数据集成验证通过！');
        console.log('\n📍 云服务器访问地址:');
        console.log(`  主应用首页: ${FRONTEND_BASE_URL}`);
        console.log(`  病历管理页面: ${FRONTEND_BASE_URL}/medical-records`);
        console.log(`  测试数据展示: ${FRONTEND_BASE_URL}/test-medical-records.html`);
        console.log(`  验证工具页面: ${FRONTEND_BASE_URL}/test-page-verification.html`);
        console.log(`  API文档: ${API_BASE_URL}/docs`);
    } else {
        console.log('\n⚠️  请检查云服务器服务状态并重试');
    }
}

// 运行验证
main().catch(console.error);
