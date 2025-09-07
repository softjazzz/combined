/**
 * API包装器工具
 * 统一处理API调用、错误处理和响应格式
 */
import type { PostgrestError } from '@supabase/supabase-js';
export interface ApiResponse<T = any> {
    success: boolean;
    data?: T;
    error?: {
        message: string;
        code?: string;
        details?: any;
    };
    count?: number;
    message?: string;
}
export interface QueryOptions {
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    filters?: Record<string, any>;
}
export declare class ApiWrapper {
    /**
     * 包装数据库查询操作
     */
    static query<T>(operation: () => Promise<{
        data: T | null;
        error: PostgrestError | null;
        count?: number | null;
    }>): Promise<ApiResponse<T>>;
    /**
     * 包装数据库插入操作
     */
    static insert<T>(operation: () => Promise<{
        data: T | null;
        error: PostgrestError | null;
    }>): Promise<ApiResponse<T>>;
    /**
     * 包装数据库更新操作
     */
    static update<T>(operation: () => Promise<{
        data: T | null;
        error: PostgrestError | null;
    }>): Promise<ApiResponse<T>>;
    /**
     * 包装数据库删除操作
     */
    static delete<T>(operation: () => Promise<{
        data: T | null;
        error: PostgrestError | null;
    }>): Promise<ApiResponse<T>>;
    /**
     * 解析 Postgrest 错误信息
     */
    private static parsePostgrestError;
    /**
     * 构建查询条件
     */
    static buildQuery(baseQuery: any, options?: QueryOptions): any;
    /**
     * 验证业务规则
     */
    static validateBusinessRule(condition: boolean, message: string): void;
    /**
     * 处理文件上传
     */
    static uploadFile(file: File, bucket: string, path: string): Promise<ApiResponse<{
        url: string;
        path: string;
    }>>;
    /**
     * 批量操作
     */
    static batchOperation<T>(operations: (() => Promise<ApiResponse<T>>)[], options?: {
        continueOnError?: boolean;
        maxConcurrency?: number;
    }): Promise<{
        success: boolean;
        results: ApiResponse<T>[];
        summary: {
            total: number;
            successful: number;
            failed: number;
        };
    }>;
}
export declare const query: typeof ApiWrapper.query, insert: typeof ApiWrapper.insert, update: typeof ApiWrapper.update, remove: typeof ApiWrapper.delete, buildQuery: typeof ApiWrapper.buildQuery, validateBusinessRule: typeof ApiWrapper.validateBusinessRule, uploadFile: typeof ApiWrapper.uploadFile, batchOperation: typeof ApiWrapper.batchOperation;
