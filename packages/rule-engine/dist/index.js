export function getByPath(obj, path) {
    return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}
export function evalClause(facts, clause) {
    const left = getByPath(facts, clause.fact);
    const op = clause.op;
    const val = clause.value;
    switch (op) {
        case '==': return left === val;
        case '!=': return left !== val;
        case '>': return typeof left === 'number' && left > val;
        case '>=': return typeof left === 'number' && left >= val;
        case '<': return typeof left === 'number' && left < val;
        case '<=': return typeof left === 'number' && left <= val;
        case 'in': return Array.isArray(val) && val.includes(left);
        case 'not_in': return Array.isArray(val) && !val.includes(left);
        default: return false;
    }
}
export function evalExpression(facts, expr) {
    if (!expr || typeof expr !== 'object')
        return false;
    if (Array.isArray(expr.all))
        return expr.all.every((sub) => evalExpression(facts, sub));
    if (Array.isArray(expr.any))
        return expr.any.some((sub) => evalExpression(facts, sub));
    return evalClause(facts, expr);
}
export function renderMessage(template, facts) {
    return template.replace(/\{([^}]+)\}/g, (_, p) => {
        const v = getByPath(facts, String(p).trim());
        return v == null ? '' : String(v);
    });
}
