# Current synthetic evidence binding: culture rules

Fixed source: `21f4a93e103a34002a1f9d36f9d895f226c0122f`. One authorized guarded run of the two unchanged original synthetic unit files collected **45 nodes: 44 passed, 1 failed** (2.64 s; exit 1; one warning). The first-run log and failed old 015 oracle are retained; there was no rerun, assertion change, skip or xfail. The slot was released after execution.

| Layer | Actual result | Rule attribution |
|---|---:|---|
| Direct native/binding/reducer synthetic status coverage | 10 passed | LX0609-06-03-03 and LX0609-06-03-04; four also reach Aggregator |
| Shared culture projection seam | 33 passed | Shared support only; no direct per-rule delivery credit |
| Positive organism parser fixture | 1 passed | LX0609-06-03-04 parser only; not complete delivery |
| Legacy full-text prompt oracle | 1 failed | LX0609-06-03-04; old 015 literal preserved |

The direct cases retain normal readable no-trigger, missing/current planned or historic culture, unavailable/truncated source, query-error, real-ref and zero-fake-client-call assertions. Parameters and per-node classification are indexed in [current-results.json](current-results.json); the original frozen plan is unchanged.

## Old 015 oracle and the current ID contract

This particular failure is a stale identity literal under an explicit four-part ID protocol. Fixed [`apps/medqc-web/docs/plans/lx0609-four-part-rule-code-mapping-v1.csv`](F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/docs/plans/lx0609-four-part-rule-code-mapping-v1.csv) lines 49/50 bind LX0609-014 to LX0609-06-03-03 and LX0609-015 to LX0609-06-03-04, both `frozen_identity_migration`; CSV blob `72262fcad59f4e4c10cffd1cbd463ff250c7490c`. Fixed `exam_lab_fact_extraction.py` blob `c14d8be7fce2a999d662025410d60e6e9a65801a` declares four-part culture IDs (line 32), rejects unsupported scopes (1163-1172), requires exact selected rule identities (1394), and uses LX0609-06-03-04 in the unchanged culture medical paragraph (1396).

Text-only AST comparison proves that replacing only `015` with `LX0609-06-03-04` in the original expected paragraph exactly matches the current prompt literal. This is explanatory evidence, not a changed assertion or additional prompt invocation; see [legacy-oracle-static.json](legacy-oracle-static.json). The observed assertion remains failed. It does not show actual clinical input truncation, and does not establish that truncation cannot occur on other inputs.

## Binding and limits

Responsible native/fact blobs and both test blobs match the historical report baseline `c3a87a4f820259bca37a01764522ea1f3f485a3c`; individual blob identities are in [replay-plan.json](replay-plan.json). That equivalence is limited to these sources and helpers, not all historic runtime dependencies. Current execution is bound separately: actual HEAD is the fixed target; pre/post hashes of source, tests, guard, runner and pytest.ini match; all 171 loaded app modules resolve within the target backend. Runner SHA256: `88e1404bb8d9fbee84668e4ef4705fd646b94a6a188baef38dccc30ed41e8b0d`. Windows stdlib platform values were cached before installing the subprocess guard; there was no support exception.

[Manifest](current-synthetic-manifest.json), [original run log](first-run.log), and [JUnit](current-synthetic.xml) preserve execution evidence. The guard blocks clinical private paths, credential files, real DB, network/model transport and post-install subprocess. No PG, env files, clinical raw records or real model were accessed. This adds current synthetic protection evidence only: it does not relabel historical real/model evidence, rerun six-case semantic extraction, or establish 45 medical passes for these two rules.
