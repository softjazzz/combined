import { customRuleCases } from './src/data/customRuleCases';
import { buildCaseText } from './src/data/qcRuleCases';
import * as fs from 'fs';

const results = [];
for (const c of customRuleCases) {
    const pText = buildCaseText(c.positive, { includeHints: false, includeTitle: false, includeAnalysis: false, includeFocusPoints: false });
    const nText = buildCaseText(c.negative, { includeHints: false, includeTitle: false, includeAnalysis: false, includeFocusPoints: false });
    results.push({
        ruleId: c.ruleId,
        documentType: c.documentType,
        positive_example: pText,
        negative_example: nText
    });
}
fs.writeFileSync('backend/lx_cases_extracted.json', JSON.stringify(results, null, 2));
console.log("Extracted", results.length, "cases to backend/lx_cases_extracted.json");
