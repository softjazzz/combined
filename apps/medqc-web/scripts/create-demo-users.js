"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg';
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseAnonKey);
const demoUsers = [
    {
        email: 'admin@demo.com',
        password: 'demo123456',
        role: 'admin',
        display_name: '系统管理员',
        department: '信息科'
    },
    {
        email: 'qc@demo.com',
        password: 'demo123456',
        role: 'qc_manager',
        display_name: '质控管理员',
        department: '质控科'
    },
    {
        email: 'doctor@demo.com',
        password: 'demo123456',
        role: 'doctor',
        display_name: '医务人员',
        department: '内科'
    }
];
async function createDemoUsers() {
    console.log('开始创建演示用户账户...\n');
    for (const userData of demoUsers) {
        try {
            console.log(`正在创建用户: ${userData.email}`);
            // 1. 先尝试登录，如果能登录说明用户存在
            const { data: signInData, error: signInError } = await supabase.auth.signInWithPassword({
                email: userData.email,
                password: userData.password
            });
            let userId;
            if (!signInError && signInData.user) {
                console.log(`✓ 用户已存在: ${userData.email}，ID: ${signInData.user.id}`);
                userId = signInData.user.id;
                // 更新用户元数据
                await supabase.auth.updateUser({
                    data: {
                        display_name: userData.display_name,
                        department: userData.department,
                        role: userData.role
                    }
                });
            }
            else {
                // 2. 如果登录失败，创建新用户
                const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
                    email: userData.email,
                    password: userData.password,
                    options: {
                        data: {
                            display_name: userData.display_name,
                            department: userData.department,
                            role: userData.role
                        }
                    }
                });
                if (signUpError || !signUpData.user) {
                    throw new Error(signUpError?.message || '创建用户失败');
                }
                userId = signUpData.user.id;
                console.log(`✓ 用户创建成功: ${userData.email}，ID: ${userId}`);
            }
            // 3. 检查并创建或更新用户角色
            const { data: existingRole } = await supabase
                .from('user_roles')
                .select('id')
                .eq('user_id', userId)
                .single();
            if (existingRole) {
                // 更新现有角色
                const { error: updateError } = await supabase
                    .from('user_roles')
                    .update({
                    role: userData.role,
                    department: userData.department,
                    hospital_id: 'demo-hospital-001'
                })
                    .eq('user_id', userId);
                if (updateError) {
                    throw new Error(`更新用户角色失败: ${updateError.message}`);
                }
                console.log(`✓ 用户角色已更新: ${userData.role}`);
            }
            else {
                // 创建新角色记录
                const { error: insertError } = await supabase
                    .from('user_roles')
                    .insert({
                    user_id: userId,
                    role: userData.role,
                    department: userData.department,
                    hospital_id: 'demo-hospital-001'
                });
                if (insertError) {
                    throw new Error(`创建用户角色失败: ${insertError.message}`);
                }
                console.log(`✓ 用户角色已创建: ${userData.role}`);
            }
            // 4. 测试登录
            const { error: testLoginError } = await supabase.auth.signInWithPassword({
                email: userData.email,
                password: userData.password
            });
            if (testLoginError) {
                console.log(`⚠️  登录测试失败: ${testLoginError.message}`);
            }
            else {
                console.log('✓ 登录测试成功');
                // 登出以便测试下一个用户
                await supabase.auth.signOut();
            }
            console.log(''); // 空行分隔
        }
        catch (error) {
            console.error(`❌ 处理用户失败 ${userData.email}:`, error.message);
            console.log(''); // 空行分隔
        }
    }
    console.log('\n🎉 演示用户创建完成！');
    console.log('现在可以使用以下账户登录系统：');
    console.log('1. 管理员: admin@demo.com / demo123456');
    console.log('2. 质控管理员: qc@demo.com / demo123456');
    console.log('3. 医务人员: doctor@demo.com / demo123456');
    console.log('\n🌐 系统访问地址：http://43.156.133.9:3000');
}
// 运行脚本
createDemoUsers().catch(console.error);
