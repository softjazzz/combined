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
async function checkRLSStatus() {
    try {
        console.log('🔍 检查RLS策略状态...\n');
        // 检查主要表的RLS状态
        const tables = [
            'medical_records',
            'qc_results',
            'qc_rules',
            'user_roles',
            'analytics_results',
            'report_instances',
            'alert_records'
        ];
        for (const tableName of tables) {
            console.log(`📋 检查表: ${tableName}`);
            // 尝试查询数据以测试访问权限
            const { data, error } = await supabase
                .from(tableName)
                .select('*')
                .limit(1);
            if (error) {
                if (error.message.includes('row-level security')) {
                    console.log(`  🔒 RLS已启用 - ${error.message}`);
                }
                else if (error.message.includes('does not exist')) {
                    console.log(`  ❌ 表不存在`);
                }
                else {
                    console.log(`  ⚠️  其他错误: ${error.message}`);
                }
            }
            else {
                console.log(`  ✅ 可正常访问 (${data?.length || 0} 条记录)`);
            }
        }
        console.log('\n🎯 RLS状态总结:');
        console.log('- 如果看到"row-level security"错误，说明RLS已启用');
        console.log('- 如果看到"可正常访问"，说明RLS可能已禁用或有开放策略');
    }
    catch (error) {
        console.error('❌ 检查RLS状态失败:', error);
    }
}
checkRLSStatus();
