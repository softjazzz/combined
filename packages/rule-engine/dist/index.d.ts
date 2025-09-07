export type AtomicClause = {
    fact: string;
    op: '==' | '!=' | '>' | '>=' | '<' | '<=' | 'in' | 'not_in';
    value: any;
};
export type Expression = {
    all?: Expression[];
    any?: Expression[];
} | AtomicClause;
export declare function getByPath(obj: any, path: string): any;
export declare function evalClause(facts: any, clause: AtomicClause): boolean;
export declare function evalExpression(facts: any, expr: Expression): boolean;
export declare function renderMessage(template: string, facts: any): string;
