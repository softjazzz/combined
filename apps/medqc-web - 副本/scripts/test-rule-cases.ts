import { qcRuleCases, buildCaseText } from '../src/data/qcRuleCases';
import axios from 'axios';
import fs from 'fs';
import path from 'path';

const API_URL = 'http://localhost:8001/api/v1/qc/sichuan/evaluate-fast';

async function testRuleCases() {
    console.log(`Loaded ${qcRuleCases.length} rules with cases.`);

    // Test 1 rule for demonstration first
    const rulesToTest = qcRuleCases.slice(0, 1);

    for (const rule of rulesToTest) {
        console.log(`\nTesting rule: ${rule.ruleId}`);

        // 1. Test Positive Case
        const positiveText = buildCaseText(rule.positive, { includeHints: false });
        console.log(`  [Positive] Document Type: ${rule.documentType}, Text length: ${positiveText.length}`);
        try {
            const posRes = await axios.post(API_URL, {
                document_id: `test_pos_${rule.ruleId}`,
                document_content: positiveText,
                document_type: rule.documentType || '病程记录',
                rule_ids: [rule.ruleId],
                prompt_mode: 'plan_a'
            });
            const results = posRes.data?.evaluation_results || [];
            console.log(`  [Positive] Evaluation Results length: ${results.length}`);
            if (results.length > 0) {
                console.log(`  [Positive] is_compliant: ${results[0].is_compliant} | status: ${results[0].status}`);
                console.log(`  [Positive] Findings: ${results[0].findings}`);
            }
        } catch (e: any) {
            console.error(`  [Positive] Error:`, e.response?.data || e.message);
        }

        // 2. Test Negative Case
        const negativeText = buildCaseText(rule.negative, { includeHints: false });
        console.log(`\n  [Negative] Document Type: ${rule.documentType}, Text length: ${negativeText.length}`);
        try {
            const negRes = await axios.post(API_URL, {
                document_id: `test_neg_${rule.ruleId}`,
                document_content: negativeText,
                document_type: rule.documentType || '病程记录',
                rule_ids: [rule.ruleId],
                prompt_mode: 'plan_a'
            });
            const results = negRes.data?.evaluation_results || [];
            console.log(`  [Negative] Evaluation Results length: ${results.length}`);
            if (results.length > 0) {
                console.log(`  [Negative] is_compliant: ${results[0].is_compliant} | status: ${results[0].status}`);
                console.log(`  [Negative] Findings: ${results[0].findings}`);
            }
        } catch (e: any) {
            console.error(`  [Negative] Error:`, e.response?.data || e.message);
        }
    }
}

testRuleCases().catch(console.error);
