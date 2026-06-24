"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * 简单的DeepSeek API测试脚本
 * 验证阿里云百炼平台连接
 */
const dotenv_1 = require("dotenv");
// 加载环境变量
(0, dotenv_1.config)();
const API_KEY = 'sk-f1fa15b00fb042a9a80943a40e142daf';
const BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
const MODEL = 'deepseek-v3';
async function testDeepSeekAPI() {
    console.log('🧪 测试阿里云百炼 DeepSeek V3 API连接...\n');
    console.log('配置信息:');
    console.log(`API Key: ${API_KEY.substring(0, 10)}...`);
    console.log(`Base URL: ${BASE_URL}`);
    console.log(`Model: ${MODEL}\n`);
    try {
        const response = await fetch(`${BASE_URL}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`
            },
            body: JSON.stringify({
                model: MODEL,
                messages: [
                    {
                        role: 'user',
                        content: '你好！请简单介绍一下你的功能和能力。'
                    }
                ],
                max_tokens: 200,
                temperature: 0.7
            })
        });
        console.log(`HTTP状态: ${response.status} ${response.statusText}`);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ API请求失败:');
            console.error(errorText);
            return;
        }
        const result = await response.json();
        console.log('✅ API连接成功!');
        console.log('\n📝 AI响应:');
        console.log(result.choices?.[0]?.message?.content || '无响应内容');
        if (result.usage) {
            console.log('\n📊 Token使用情况:');
            console.log(`输入Token: ${result.usage.prompt_tokens}`);
            console.log(`输出Token: ${result.usage.completion_tokens}`);
            console.log(`总Token: ${result.usage.total_tokens}`);
        }
    }
    catch (error) {
        console.error('❌ 网络错误:', error);
    }
}
// 运行测试
testDeepSeekAPI().catch(console.error);
