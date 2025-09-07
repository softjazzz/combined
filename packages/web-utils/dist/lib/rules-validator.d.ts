export interface ValidationResult {
    isValid: boolean;
    errors: string[];
    warnings: string[];
}
export interface RuleData {
    rule_code: string;
    name: string;
    description: string;
    category: string;
    rule_type: string;
    severity: string;
    max_score: number;
    weight: number;
    check_logic: Record<string, any>;
    prompt_template?: string;
    version: string;
}
/**
 * 规则验证器类
 */
export declare class RulesValidator {
    static validateRuleCode(ruleCode: string): ValidationResult;
    /**
     * 验证规则名称
     */
    static validateRuleName(name: string): ValidationResult;
    /**
     * 验证规则描述
     */
    static validateRuleDescription(description: string): ValidationResult;
    /**
     * 验证规则分类
     */
    static validateRuleCategory(category: string): ValidationResult;
    /**
     * 验证规则类型
     */
    static validateRuleType(ruleType: string): ValidationResult;
    /**
     * 验证严重程度
     */
    static validateRuleSeverity(severity: string): ValidationResult;
    /**
     * 验证最大扣分
     */
    static validateMaxScore(maxScore: number, severity: string): ValidationResult;
    /**
     * 验证权重
     */
    static validateWeight(weight: number): ValidationResult;
    /**
     * 验证检查逻辑
     */
    static validateCheckLogic(checkLogic: Record<string, any>): ValidationResult;
    /**
     * 验证提示模板
     */
    static validatePromptTemplate(template?: string): ValidationResult;
    /**
     * 验证版本号
     */
    static validateVersion(version: string): ValidationResult;
    /**
     * 综合验证规则
     */
    static validateRule(rule: RuleData): ValidationResult;
    /**
     * 批量验证规则
     */
    static validateRules(rules: RuleData[]): {
        [ruleCode: string]: ValidationResult;
    };
}
