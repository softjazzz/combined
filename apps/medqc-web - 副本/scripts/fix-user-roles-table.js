"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const supabase_js_1 = require("@supabase/supabase-js");
const dotenv = __importStar(require("dotenv"));
// 加载环境变量
dotenv.config();
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
const supabase = (0, supabase_js_1.createClient)(supabaseUrl, supabaseKey);
async function fixUserRolesTable() {
    try {
        console.log('🔧 修复 user_roles 表结构...');
        // 检查 department 字段是否存在
        const { data: testData, error: testError } = await supabase
            .from('user_roles')
            .select('department')
            .limit(1);
        if (testError && testError.message.includes('does not exist')) {
            console.log('📝 添加 department 字段...');
            // 添加 department 字段
            const { error: alterError } = await supabase.rpc('exec_sql', {
                sql: 'ALTER TABLE user_roles ADD COLUMN department VARCHAR(50);'
            });
            if (alterError) {
                console.log('⚠️  无法使用 rpc 添加字段，尝试直接执行...');
                // 如果 rpc 不可用，我们需要手动在 Supabase Dashboard 中执行
                console.log('🔧 请在 Supabase Dashboard 的 SQL Editor 中执行以下 SQL:');
                console.log('ALTER TABLE user_roles ADD COLUMN department VARCHAR(50);');
                return;
            }
            console.log('✅ department 字段添加成功');
        }
        else {
            console.log('✅ department 字段已存在');
        }
        // 验证修复结果
        const { data: verifyData, error: verifyError } = await supabase
            .from('user_roles')
            .select('id, user_id, role, department')
            .limit(1);
        if (verifyError) {
            console.error('❌ 验证失败:', verifyError);
        }
        else {
            console.log('✅ 表结构修复完成，可以正常查询 department 字段');
        }
    }
    catch (error) {
        console.error('❌ 修复失败:', error);
    }
}
fixUserRolesTable();
