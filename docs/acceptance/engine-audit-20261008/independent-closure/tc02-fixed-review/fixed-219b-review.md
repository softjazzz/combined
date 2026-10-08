# TC02 fixed-219b independent review

**Do not serially integrate 219b13d5881e106a4780e0d9ba1f12620d7e3900 yet. Confirmed P1 blocker TC02-PV01 breaks the formal model input view.** This conclusion is limited to engineering, not clinical acceptance.

Baseline fac4ef67c0f68da1625f419ea5dddb47f38aa78b. Fixed HEAD and clean worktree verified at F:/MedQC-worktrees/qc-fix-critical-v2-20261008. All 11 changed paths reviewed, all 10 tested source/test/JSON hashes match the final author manifest. Shared changes are confined to 070; global projector, binding, evidence store and public DTO are unchanged. No reviewer production/test edits or suite rerun.

## Confirmed blocker: formal privacy view

The helper redacts the real multiline body at extended_document/transfusion_performance_extraction.py:138 and serializes its body/spans at :153. The actual formal wrapper at llm_prompt_privacy.py:418 redacts the whole JSON-containing prompt again. The address value regex at :61 excludes a real newline, but JSON carries an escaped backslash-n. It can therefore match an already-redacted address placeholder plus the following clinical action and JSON structure. The validator still uses the initial helper view. Object-level wrapper idempotence is not string/view idempotence.

Root-authorized pure stdlib synthetic capture used the exact helper function/prompt construction and actual privacy wrapper. Only relative imports were removed to avoid application imports; exact redactor was injected. Capture fakes returned fixed unknown JSON, not medical answers. Neither PG, env, model, network nor pytest was used. Frozen expectation was printed before captures: address redaction must preserve following medical action, valid JSON, and equal transmitted body/span view. One direct fake and one actual-wrapper delegate call completed; test slot released.

Synthetic input: address label + synthetic street + real newline + `14:00` + completed RBC infusion; record_time `2026-01-01 14:00:00`. Full Unicode-escaped synthetic input and method are in the JSON report. Initial INPUT_JSON parsed and preserved the action. Actual wrapper delegate prompt lost the action and INPUT_JSON raised JSONDecodeError. Prompt hash changed from fff654ef9cfcd60d22a35e0114d11bf41ae8065fdd4fe3c91f7e2555c2f91421 to 02643b3cfbe254df3ed3eb1015d9c6cd90da77093f0c439a5e73a44c40268b0a. Exact helper SHA256 cbc66468d12e4e47a44eec52dd27c5a29edfa7f4989f3ebeafd2740ce1607d2b; privacy SHA256 e4cbf47d9971fad10fcefd04077528a1fde55f5281a65b1787d7e7852ee04219.

Execution resources carry the formally wrapped client into native extended-document execution. New TC02 tests invoke native directly with an unwrapped PerformanceFake and omit this boundary. No identity leak or real-model downstream behavior is inferred. The demonstrated defect is lost clinical input plus invalid serialization and a divergent coordinate view.

Before integration, preserve privacy validation while ensuring exactly one body/span view is both transmitted and parsed. Add actual wrapper coverage for this frozen input and a benign normal control; do not disable privacy checks or change medical expectations to fit damaged input. Root/owner should select the narrow repair. This reviewer did not implement a repair.

## Fixed engineering checks accepted

Author evidence green-compatible-refs.log/.xml: 202 passed, 0 failure/error/skip, 4.48s. Independent read checked XML and source manifest; no suite rerun. Log SHA256 d365252477b0beec19465f8850cfd62cc56048f7bb544df074b9153d933fae78; XML 7adafbcc195ab7be3db32371ad196cd692fed7faa58aaf16a8e1e7dfddac3bc1; manifest 31c3c92c452deb67a44957cc4f6a85d2b993d43d714671dbf079be3e7e9d48f9. Directory: F:/MedQC-worktrees/qc-fix-critical-v2-20261008/.tmp/tc02-closure/.

- One bounded optional batch for dedicated records; trusted MR path zero calls; controlled performed/plan/cancel/unknown, no expanded negation vocabulary.
- Known NC plus unknown retained, C plus unknown and all-cancel gap, original no-sources NA; raw count exact int 1..100 only NC complete facts, illegal raw values rejected before filtering/save.
- Exact references only when no actual, consumed dedicated rows and no source error. Actual/MR retains original source summaries plus consumed rows. Original multi-event strict union and medical assertions remain.
- Four new MR expected reference sets corrected in separate v2 freeze from independent snapshot inputs: four source summaries plus twelve rows. Original v1 retained, not overwritten or generated from executor output.
- Original cancel_gap precise SQLite-card assertion retained and passed; correct source ID/time/field/excerpt and reload are covered. This fixes that canceled-path consumed-reference defect. Native refs alone are not substituted for exact public cards.

Previous evidence remains: 78 setup errors; 83 run 82/1 cancel card; 202 run 192/10 refs; 202 run 201/1 old multi-event refs. Latest green does not erase them. See cancel-gap-evidence-review.md/.json for corrected actual Finalizer/projector reachability, and original/v2 freezes under F:/MedQC-worktrees/review-artifacts/tc02-design/.

## Open limits

Real-model extraction and clinical semantics remain unverified. Single state for ambiguous multi-event/cross-day/same-clock/no-clock text remains a semantic boundary. Normal C missing laboratory document IDs has the inherited exact-coordinate limitation; it is separate from new canceled-path refs and not closed here. CDM time semantics are inherited, hospital ETL not independently validated. This scope does not close TC01, TC03, TR044 multi-event, or excluded 0916. No original patient material is in this report.
