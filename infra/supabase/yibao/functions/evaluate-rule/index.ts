// Deno Edge Function: evaluate-rule
// Minimal, stateless evaluator for JSON expressions with message rendering
// POST body: { facts: any, expression: Expression, messageTemplate?: string }

type AtomicClause = { fact: string; op: '=='|'!='|'>'|'>='|'<'|'<='|'in'|'not_in'; value: unknown }
type Expression = { all?: Expression[]; any?: Expression[] } | AtomicClause

function getByPath(obj: unknown, path: string): unknown {
  return String(path).split('.').reduce((acc: any, key: string) => (acc == null ? undefined : acc[key]), obj as any)
}

function evalClause(facts: unknown, clause: AtomicClause): boolean {
  const left = getByPath(facts, clause.fact)
  const op = clause.op
  const val = (clause as any).value
  switch (op) {
    case '==': return left === val
    case '!=': return left !== val
    case '>': return typeof left === 'number' && typeof val === 'number' && left > val
    case '>=': return typeof left === 'number' && typeof val === 'number' && left >= val
    case '<': return typeof left === 'number' && typeof val === 'number' && left < val
    case '<=': return typeof left === 'number' && typeof val === 'number' && left <= val
    case 'in': return Array.isArray(val) && val.includes(left)
    case 'not_in': return Array.isArray(val) && !val.includes(left)
    default: return false
  }
}

function evalExpression(facts: unknown, expr: Expression): boolean {
  if (!expr || typeof expr !== 'object') return false
  if (Array.isArray((expr as any).all)) return ((expr as any).all as any[]).every((sub) => evalExpression(facts, sub))
  if (Array.isArray((expr as any).any)) return ((expr as any).any as any[]).some((sub) => evalExpression(facts, sub))
  return evalClause(facts, expr as AtomicClause)
}

function renderMessage(template: string, facts: unknown): string {
  return String(template || '').replace(/\{([^}]+)\}/g, (_: string, p: string) => {
    const v = getByPath(facts, String(p).trim())
    return v == null ? '' : String(v)
  })
}

export const handler = async (req: Request): Promise<Response> => {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 })
  }
  try {
    const { facts, expression, messageTemplate } = await req.json()
    const matched = evalExpression(facts, expression as Expression)
    const message = matched && messageTemplate ? renderMessage(messageTemplate, facts) : ''
    return new Response(JSON.stringify({ matched, message }), { headers: { 'Content-Type': 'application/json' } })
  } catch (e) {
    return new Response(JSON.stringify({ error: (e as Error)?.message || 'Invalid payload' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
  }
}

// For local dev via deno run
if (import.meta.main) {
  const port = 54321
  const server = Deno.serve({ port }, handler)
  console.log(`evaluate-rule listening on http://localhost:${port}`)
  await server.finished
}



