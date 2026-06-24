"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg';
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseAnonKey);
async function testLogin() {
    console.log('🔐 测试登录功能...\n');
    try {
        // 测试医生账号登录
        const { data, error } = await supabase.auth.signInWithPassword({
            email: 'doctor@demo.com',
            password: 'demo123456'
        });
        if (error) {
            console.error('❌ 登录失败:', error.message);
            // 如果用户不存在，尝试创建
            if (error.message.includes('Invalid login credentials')) {
                console.log('🔄 尝试创建测试用户...');
                const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
                    email: 'doctor@demo.com',
                    password: 'demo123456',
                    options: {
                        data: {
                            display_name: '张医生',
                            department: '内科',
                            roles: ['doctor']
                        }
                    }
                });
                if (signUpError) {
                    console.error('❌ 创建用户失败:', signUpError.message);
                }
                else {
                    console.log('✅ 测试用户创建成功');
                    console.log('用户信息:', signUpData.user?.email);
                }
            }
        }
        else {
            console.log('✅ 登录成功!');
            console.log('用户信息:', {
                email: data.user?.email,
                id: data.user?.id,
                metadata: data.user?.user_metadata
            });
            // 登出
            await supabase.auth.signOut();
            console.log('✅ 已登出');
        }
    }
    catch (error) {
        console.error('❌ 测试失败:', error.message);
    }
}
// 运行测试
testLogin().catch(console.error);
