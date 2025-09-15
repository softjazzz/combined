// 本地规则引擎实现，替代 @health-qc/rule-engine

export interface RuleContext {
  [key: string]: any
}

export interface RuleExpression {
  type: 'comparison' | 'logical' | 'value' | 'field'
  operator?: string
  left?: RuleExpression
  right?: RuleExpression
  value?: any
  field?: string
}

/**
 * 评估规则表达式
 */
export function evalExpression(expression: RuleExpression | string, context: RuleContext): boolean {
  try {
    if (typeof expression === 'string') {
      // 简单的字符串表达式解析
      return evaluateStringExpression(expression, context)
    }

    if (!expression || typeof expression !== 'object') {
      return false
    }

    switch (expression.type) {
      case 'value':
        return !!expression.value

      case 'field':
        return !!context[expression.field || '']

      case 'comparison':
        return evaluateComparison(expression, context)

      case 'logical':
        return evaluateLogical(expression, context)

      default:
        return false
    }
  } catch (error) {
    console.warn('规则表达式评估失败:', error)
    return false
  }
}

/**
 * 评估比较表达式
 */
function evaluateComparison(expression: RuleExpression, context: RuleContext): boolean {
  if (!expression.left || !expression.right || !expression.operator) {
    return false
  }

  const leftValue = getExpressionValue(expression.left, context)
  const rightValue = getExpressionValue(expression.right, context)

  switch (expression.operator) {
    case '==':
    case '===':
      return leftValue === rightValue
    case '!=':
    case '!==':
      return leftValue !== rightValue
    case '>':
      return Number(leftValue) > Number(rightValue)
    case '>=':
      return Number(leftValue) >= Number(rightValue)
    case '<':
      return Number(leftValue) < Number(rightValue)
    case '<=':
      return Number(leftValue) <= Number(rightValue)
    case 'contains':
      return String(leftValue).includes(String(rightValue))
    case 'startsWith':
      return String(leftValue).startsWith(String(rightValue))
    case 'endsWith':
      return String(leftValue).endsWith(String(rightValue))
    default:
      return false
  }
}

/**
 * 评估逻辑表达式
 */
function evaluateLogical(expression: RuleExpression, context: RuleContext): boolean {
  if (!expression.operator) {
    return false
  }

  switch (expression.operator) {
    case 'AND':
    case '&&':
      return expression.left ? evalExpression(expression.left, context) : false &&
             expression.right ? evalExpression(expression.right, context) : false

    case 'OR':
    case '||':
      return expression.left ? evalExpression(expression.left, context) : false ||
             expression.right ? evalExpression(expression.right, context) : false

    case 'NOT':
    case '!':
      return expression.left ? !evalExpression(expression.left, context) : false

    default:
      return false
  }
}

/**
 * 获取表达式的值
 */
function getExpressionValue(expression: RuleExpression, context: RuleContext): any {
  switch (expression.type) {
    case 'value':
      return expression.value

    case 'field':
      return context[expression.field || '']

    case 'comparison':
      return evaluateComparison(expression, context)

    case 'logical':
      return evaluateLogical(expression, context)

    default:
      return null
  }
}

/**
 * 评估字符串表达式（简单实现）
 */
function evaluateStringExpression(expression: string, context: RuleContext): boolean {
  try {
    // 替换上下文变量
    let processedExpression = expression
    
    // 查找并替换 ${variable} 格式的变量
    const variableRegex = /\$\{([^}]+)\}/g
    processedExpression = processedExpression.replace(variableRegex, (match, variable) => {
      const value = context[variable.trim()]
      return value !== undefined ? String(value) : match
    })

    // 简单的布尔表达式评估
    if (processedExpression === 'true') return true
    if (processedExpression === 'false') return false
    
    // 数字比较
    const numberComparison = /^(\d+(?:\.\d+)?)\s*(>=|<=|>|<|==|!=)\s*(\d+(?:\.\d+)?)$/.exec(processedExpression)
    if (numberComparison) {
      const [, left, operator, right] = numberComparison
      const leftNum = parseFloat(left)
      const rightNum = parseFloat(right)
      
      switch (operator) {
        case '>': return leftNum > rightNum
        case '>=': return leftNum >= rightNum
        case '<': return leftNum < rightNum
        case '<=': return leftNum <= rightNum
        case '==': return leftNum === rightNum
        case '!=': return leftNum !== rightNum
      }
    }

    return false
  } catch (error) {
    console.warn('字符串表达式评估失败:', error)
    return false
  }
}

/**
 * 渲染消息模板
 */
export function renderMessage(template: string, context: RuleContext): string {
  try {
    if (!template || typeof template !== 'string') {
      return ''
    }

    // 替换 ${variable} 格式的变量
    return template.replace(/\$\{([^}]+)\}/g, (match, variable) => {
      const keys = variable.trim().split('.')
      let value = context
      
      for (const key of keys) {
        if (value && typeof value === 'object' && key in value) {
          value = value[key]
        } else {
          return match // 保持原样如果找不到变量
        }
      }
      
      return value !== undefined && value !== null ? String(value) : match
    })
  } catch (error) {
    console.warn('消息模板渲染失败:', error)
    return template
  }
}

/**
 * 验证规则表达式的有效性
 */
export function validateExpression(expression: RuleExpression | string): boolean {
  try {
    if (typeof expression === 'string') {
      return expression.length > 0
    }

    if (!expression || typeof expression !== 'object') {
      return false
    }

    switch (expression.type) {
      case 'value':
        return expression.value !== undefined

      case 'field':
        return !!expression.field

      case 'comparison':
        return !!(expression.operator && expression.left && expression.right)

      case 'logical':
        return !!(expression.operator && (expression.left || expression.right))

      default:
        return false
    }
  } catch (error) {
    return false
  }
}

/**
 * 创建简单的比较表达式
 */
export function createComparison(field: string, operator: string, value: any): RuleExpression {
  return {
    type: 'comparison',
    operator,
    left: { type: 'field', field },
    right: { type: 'value', value }
  }
}

/**
 * 创建逻辑表达式
 */
export function createLogical(operator: string, left: RuleExpression, right?: RuleExpression): RuleExpression {
  return {
    type: 'logical',
    operator,
    left,
    right
  }
}
