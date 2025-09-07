/**
 * 格式化相对时间
 * @param dateString 日期字符串
 * @returns 相对时间描述
 */
export declare function formatRelativeTime(dateString: string): string;
/**
 * 格式化日期为标准格式
 * @param dateString 日期字符串
 * @param format 格式类型
 * @returns 格式化后的日期字符串
 */
export declare function formatDate(dateString: string, format?: 'date' | 'datetime' | 'time'): string;
/**
 * 计算两个日期之间的天数差
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 天数差
 */
export declare function getDaysDifference(startDate: string, endDate: string): number;
/**
 * 检查日期是否过期
 * @param dateString 日期字符串
 * @returns 是否过期
 */
export declare function isExpired(dateString: string): boolean;
/**
 * 获取日期范围描述
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 日期范围描述
 */
export declare function getDateRangeDescription(startDate: string, endDate: string): string;
/**
 * 获取当前时间戳
 * @returns ISO格式的时间戳
 */
export declare function getCurrentTimestamp(): string;
/**
 * 添加天数到日期
 * @param dateString 原始日期
 * @param days 要添加的天数
 * @returns 新的日期字符串
 */
export declare function addDays(dateString: string, days: number): string;
/**
 * 获取本周的开始和结束日期
 * @returns 本周的日期范围
 */
export declare function getThisWeekRange(): {
    start: string;
    end: string;
};
/**
 * 获取本月的开始和结束日期
 * @returns 本月的日期范围
 */
export declare function getThisMonthRange(): {
    start: string;
    end: string;
};
/**
 * 检查时间是否在工作时间内
 * @param dateString 日期字符串
 * @param workHours 工作时间配置
 * @returns 是否在工作时间内
 */
export declare function isWorkingHours(dateString: string, workHours?: {
    start: string;
    end: string;
}): boolean;
/**
 * 格式化持续时间
 * @param minutes 分钟数
 * @returns 格式化的持续时间
 */
export declare function formatDuration(minutes: number): string;
/**
 * 获取友好的日期描述
 * @param dateString 日期字符串
 * @returns 友好的日期描述
 */
export declare function getFriendlyDate(dateString: string): string;
