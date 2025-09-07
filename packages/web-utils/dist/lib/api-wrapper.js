/**
 * API包装器工具
 * 统一处理API调用、错误处理和响应格式
 */
import { supabase } from './supabase';
import { handleDatabaseError, handleNetworkError, handleBusinessError } from './error-handler';
// API包装器类
export class ApiWrapper {
    /**
     * 包装数据库查询操作
     */
    static async query(operation) {
        try {
            const result = await operation();
            if (result.error) {
                const errorMessage = this.parsePostgrestError(result.error);
                handleDatabaseError(new Error(errorMessage), {
                    code: result.error.code,
                    details: result.error.details,
                    hint: result.error.hint
                });
                return {
                    success: false,
                    error: {
                        message: errorMessage,
                        code: result.error.code,
                        details: result.error.details
                    }
                };
            }
            return {
                success: true,
                data: result.data || undefined,
                count: result.count || undefined
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : '未知错误';
            handleNetworkError(error, { operation: 'database_query' });
            return {
                success: false,
                error: {
                    message: errorMessage
                }
            };
        }
    }
    /**
     * 包装数据库插入操作
     */
    static async insert(operation) {
        try {
            const result = await operation();
            if (result.error) {
                const errorMessage = this.parsePostgrestError(result.error);
                handleDatabaseError(new Error(errorMessage), {
                    code: result.error.code,
                    details: result.error.details,
                    hint: result.error.hint
                });
                return {
                    success: false,
                    error: {
                        message: errorMessage,
                        code: result.error.code,
                        details: result.error.details
                    }
                };
            }
            return {
                success: true,
                data: result.data || undefined,
                message: '创建成功'
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : '创建失败';
            handleNetworkError(error, { operation: 'database_insert' });
            return {
                success: false,
                error: {
                    message: errorMessage
                }
            };
        }
    }
    /**
     * 包装数据库更新操作
     */
    static async update(operation) {
        try {
            const result = await operation();
            if (result.error) {
                const errorMessage = this.parsePostgrestError(result.error);
                handleDatabaseError(new Error(errorMessage), {
                    code: result.error.code,
                    details: result.error.details,
                    hint: result.error.hint
                });
                return {
                    success: false,
                    error: {
                        message: errorMessage,
                        code: result.error.code,
                        details: result.error.details
                    }
                };
            }
            return {
                success: true,
                data: result.data || undefined,
                message: '更新成功'
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : '更新失败';
            handleNetworkError(error, { operation: 'database_update' });
            return {
                success: false,
                error: {
                    message: errorMessage
                }
            };
        }
    }
    /**
     * 包装数据库删除操作
     */
    static async delete(operation) {
        try {
            const result = await operation();
            if (result.error) {
                const errorMessage = this.parsePostgrestError(result.error);
                handleDatabaseError(new Error(errorMessage), {
                    code: result.error.code,
                    details: result.error.details,
                    hint: result.error.hint
                });
                return {
                    success: false,
                    error: {
                        message: errorMessage,
                        code: result.error.code,
                        details: result.error.details
                    }
                };
            }
            return {
                success: true,
                data: result.data || undefined,
                message: '删除成功'
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : '删除失败';
            handleNetworkError(error, { operation: 'database_delete' });
            return {
                success: false,
                error: {
                    message: errorMessage
                }
            };
        }
    }
    /**
     * 解析 Postgrest 错误信息
     */
    static parsePostgrestError(error) {
        // 常见错误码映射
        const errorMessages = {
            '23505': '数据已存在，请检查输入信息',
            '23503': '数据关联错误，请检查相关记录',
            '23502': '必填字段不能为空',
            '23514': '数据格式不符合要求',
            '42P01': '数据表不存在',
            '42703': '字段不存在',
            '42601': 'SQL语法错误',
            '08003': '数据库连接已关闭',
            '08006': '数据库连接失败',
            '53300': '数据库连接过多',
            'PGRST116': '请求格式错误',
            'PGRST301': '无权限访问',
            'PGRST302': '资源不存在'
        };
        // 根据错误码返回友好信息
        if (error.code && errorMessages[error.code]) {
            return errorMessages[error.code];
        }
        // 根据错误信息关键词判断
        const message = error.message.toLowerCase();
        if (message.includes('duplicate') || message.includes('unique')) {
            return '数据已存在，请检查输入信息';
        }
        if (message.includes('foreign key') || message.includes('violates')) {
            return '数据关联错误，请检查相关记录';
        }
        if (message.includes('not null') || message.includes('required')) {
            return '必填字段不能为空';
        }
        if (message.includes('permission') || message.includes('denied')) {
            return '权限不足，无法执行此操作';
        }
        if (message.includes('connection') || message.includes('timeout')) {
            return '数据库连接失败，请稍后重试';
        }
        // 返回原始错误信息
        return error.message || '数据库操作失败';
    }
    /**
     * 构建查询条件
     */
    static buildQuery(baseQuery, options) {
        let query = baseQuery;
        // 添加过滤条件
        if (options?.filters) {
            Object.entries(options.filters).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    if (typeof value === 'string' && value.includes('%')) {
                        query = query.ilike(key, value);
                    }
                    else if (Array.isArray(value)) {
                        query = query.in(key, value);
                    }
                    else {
                        query = query.eq(key, value);
                    }
                }
            });
        }
        // 添加排序
        if (options?.sortBy) {
            const ascending = options.sortOrder === 'asc';
            query = query.order(options.sortBy, { ascending });
        }
        // 添加分页
        if (options?.page && options?.pageSize) {
            const start = (options.page - 1) * options.pageSize;
            const end = start + options.pageSize - 1;
            query = query.range(start, end);
        }
        return query;
    }
    /**
     * 验证业务规则
     */
    static validateBusinessRule(condition, message) {
        if (!condition) {
            handleBusinessError(message);
            throw new Error(message);
        }
    }
    /**
     * 处理文件上传
     */
    static async uploadFile(file, bucket, path) {
        try {
            // 验证文件
            if (!file) {
                return {
                    success: false,
                    error: { message: '请选择要上传的文件' }
                };
            }
            // 上传文件
            const { data, error } = await supabase.storage
                .from(bucket)
                .upload(path, file, {
                cacheControl: '3600',
                upsert: false
            });
            if (error) {
                handleDatabaseError(error, { operation: 'file_upload' });
                return {
                    success: false,
                    error: { message: '文件上传失败' }
                };
            }
            // 获取公共URL
            const { data: urlData } = supabase.storage
                .from(bucket)
                .getPublicUrl(path);
            return {
                success: true,
                data: {
                    url: urlData.publicUrl,
                    path: data.path
                },
                message: '文件上传成功'
            };
        }
        catch (error) {
            handleNetworkError(error, { operation: 'file_upload' });
            return {
                success: false,
                error: { message: '文件上传失败' }
            };
        }
    }
    /**
     * 批量操作
     */
    static async batchOperation(operations, options) {
        const results = [];
        const { continueOnError = true, maxConcurrency = 5 } = options || {};
        // 分批执行操作
        for (let i = 0; i < operations.length; i += maxConcurrency) {
            const batch = operations.slice(i, i + maxConcurrency);
            const batchPromises = batch.map(async (operation) => {
                try {
                    return await operation();
                }
                catch (error) {
                    return {
                        success: false,
                        error: { message: error instanceof Error ? error.message : '操作失败' }
                    };
                }
            });
            const batchResults = await Promise.all(batchPromises);
            results.push(...batchResults);
            // 如果不继续错误且有失败的操作，则停止
            if (!continueOnError && batchResults.some(r => !r.success)) {
                break;
            }
        }
        const successful = results.filter(r => r.success).length;
        const failed = results.length - successful;
        return {
            success: failed === 0,
            results,
            summary: {
                total: results.length,
                successful,
                failed
            }
        };
    }
}
// 导出便捷函数
export const { query, insert, update, delete: remove, buildQuery, validateBusinessRule, uploadFile, batchOperation } = ApiWrapper;
