// Supabase 配置示例
// 复制此文件为 supabase-config.ts 并填入真实值

export const supabaseConfig = {
  url: 'https://your-project.supabase.co',
  anonKey: 'your-anon-key',
  serviceRoleKey: 'your-service-role-key', // 仅服务端使用
  
  // 数据库配置
  database: {
    host: 'db.your-project.supabase.co',
    port: 5432,
    database: 'postgres',
    schema: 'public'
  },
  
  // 应用配置
  app: {
    name: '智慧医保临床实时质控系统',
    version: '1.0.0'
  }
}

// 环境变量映射
export const getSupabaseUrl = () => 
  import.meta.env.VITE_SUPABASE_URL || supabaseConfig.url

export const getSupabaseAnonKey = () => 
  import.meta.env.VITE_SUPABASE_ANON_KEY || supabaseConfig.anonKey
