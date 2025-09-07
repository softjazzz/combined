import { evalExpression, renderMessage } from './index'

const facts = { patient: { age: 18 }, order: { drug_code: 'ABC001' } }
const expr = { all: [ { fact: 'patient.age', op: '>', value: 14 }, { fact: 'order.drug_code', op: 'in', value: ['ABC001','ABC002'] } ] }

const matched = evalExpression(facts, expr as any)
if (!matched) {
  console.error('evalExpression failed')
  process.exit(1)
}

const msg = renderMessage('药品 {order.drug_code} 年龄 {patient.age}', facts)
if (!msg.includes('ABC001') || !msg.includes('18')) {
  console.error('renderMessage failed')
  process.exit(1)
}

console.log('rule-engine tests passed')



