export type AtomicClause = { fact: string; op: '=='|'!='|'>'|'>='|'<'|'<='|'in'|'not_in'; value: any }
export type Expression = { all?: Expression[]; any?: Expression[] } | AtomicClause

export function getByPath(obj: any, path: string): any {
  return path.split('.').reduce((acc: any, key: string) => (acc == null ? undefined : acc[key]), obj)
}

export function evalClause(facts: any, clause: AtomicClause): boolean {
  const left = getByPath(facts, clause.fact)
  const op = clause.op
  const val = (clause as any).value
  switch (op) {
    case '==': return left === val
    case '!=': return left !== val
    case '>': return typeof left === 'number' && left > val
    case '>=': return typeof left === 'number' && left >= val
    case '<': return typeof left === 'number' && left < val
    case '<=': return typeof left === 'number' && left <= val
    case 'in': return Array.isArray(val) && val.includes(left)
    case 'not_in': return Array.isArray(val) && !val.includes(left)
    default: return false
  }
}

export function evalExpression(facts: any, expr: Expression): boolean {
  if (!expr || typeof expr !== 'object') return false
  if (Array.isArray((expr as any).all)) return ((expr as any).all as any[]).every((sub) => evalExpression(facts, sub))
  if (Array.isArray((expr as any).any)) return ((expr as any).any as any[]).some((sub) => evalExpression(facts, sub))
  return evalClause(facts, expr as AtomicClause)
}

export function renderMessage(template: string, facts: any): string {
  return template.replace(/\{([^}]+)\}/g, (_, p) => {
    const v = getByPath(facts, String(p).trim())
    return v == null ? '' : String(v)
  })
}
