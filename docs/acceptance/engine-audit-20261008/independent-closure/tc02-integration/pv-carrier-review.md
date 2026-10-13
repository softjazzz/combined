# TC02-PV01 fixed-196d independent acceptance

**Limited engineering acceptance: serial integration of 219b13d5881e106a4780e0d9ba1f12620d7e3900 followed by 196d330606285602b0b606a5b9c8ab229a15c907 is recommended. No confirmed new blocker remains in this scope.** TC02-PV01 and the frozen marker-carrier boundary are closed for engineering inputs and actual formal-wrapper coverage. This does not constitute real-model or clinical acceptance.

Fixed final HEAD196d has parent219b and exactly three changed paths: extractor, dedicated TC02 tests and acceptance document. Clean worktree independently checked. All ten privacy-length-green manifest hashes were compared to final Git blob bytes and working-file bytes; all match. Helper SHA256565677134bf214c5446e3a27621a075603665842bad86a8c14c930edb8870c93; test76417d12c4eba197cb7b547731317a17f68728a45beec84a87c1cffdaa92fd61. Actual hook log4784bd992d61e7bfc2baa8779907368b3de1fe1179f86ce49e9cc34998e25bd5 records staged encoding pass for all three texts and commit success; tested blobs unchanged.

Final author run:289/289pass,0failure/error/skip,9.898seconds, original284 plus five marker protections. Reviewer independently read XML/log/manifest and did not rerun tests. Final log SHA256eb8a085e3710f133514fb3f3cbd40b0e67f3b4996ca172a2fae964417483b340; XML486712e53b395a73219c87e2cc4cdaf80726346f6ecd6e1097884fcad79fd7ca; manifestc4957d6b47cda7838382ad42c03277cab88776ab0b86ac67c6cb1c4827136f6a. Absolute evidence directory F:/MedQC-worktrees/qc-fix-critical-v2-20261008/.tmp/tc02-closure/.

The final narrow delta adds explicit metadata-order/character-count consumption at helper line166. Test reader matches each controlled begin marker at its cursor, consumes exactly body_char_count characters, matches the true trailing delimiter at the calculated endpoint and requires the entire carrier consumed. Embedded literal or near marker strings stay source data. Five protections use original independent frozen rows/time/quotes without ID adaptation or new medical classification: own legitimate and wrong-document quotes, plus trailing-space/wrong-ID/literal-escaped-newline near markers. Exact original 21 top-level test-function ASTs and _quote/_event_time_matches/_parsed/_unique_object ASTs are unchanged from219b; marker constants exactly match independent frozen artifact. No clinical assertion was changed to pass.

Formal wrapper and known-identity checks remain intact; metadata sends parsed standard time/null only, body uses actual newlines and matches validated spans. No global privacy, native070 decision, mapping, renderer, Finalizer, rules JSON or contract JSON delta in196d. Original PV01 counterexample, red13=8/5,284green, all earlier202/83 failures and v1/v2 freezes remain archived.

Open limits remain: real model/clinical semantics unverified; normal C missing laboratory document IDs retains its inherited precise-card limitation; ambiguous clinical multi-event/cross-day/no-clock scope remains open. No broader rule-family or0916 completion implied. No reviewer production edits, new suite runs, env,PG,network or model calls. Earlier WIP notes below are retained history; their pending-binding and marker-consumer statements are superseded by this fixed section.

## Earlier WIP evidence (retained history)
# TC02-PV01 carrier A independent review (WIP)

**Reviewed WIP has no confirmed new production blocker. Fixed-commit acceptance is still pending.** Original 219b privacy-view blocker is addressed for the frozen engineering cases by carrier A and actual formal-wrapper coverage. Literal marker collision requires an explicit consuming contract/test boundary; it did not demonstrate a production quote/source mix-up in the authorized probe.

Based on 219b13d5881e106a4780e0d9ba1f12620d7e3900 in F:/MedQC-worktrees/qc-fix-critical-v2-20261008. Read extractor SHA256 1c7f8b5707853f915782131995b43502493dad5d2d82705c78181cad50889ef4, tests e8434f84e2e93c83f76b820035bf3cf457865115d00962621d0b040c2555d730. Global privacy module e4cbf47d9971fad10fcefd04077528a1fde55f5281a65b1787d7e7852ee04219 is unchanged. Reviewer changed only these assigned report files.

## Carrier and medical contract

At extractor lines143-153, metadata contains controlled dN references, span ID, Python character count and existing _parse_datetime normalized isoformat time or null. Raw record_time stays local for original Python checks. Arbitrary original strings do not enter metadata. Body is supplied between real-newline SPAN_BEGIN/END markers, using the same redacted body/span view that _quote/_parsed validate. Input instructions define zero-based body coordinates and exclude delimiter newlines.

Global privacy wrapper is still invoked and unchanged; known identity residue still fails before delegate generation. Normalized time/null avoids unnecessarily transmitting invalid raw source strings. This does not claim an old raw-time identity-gate rejection was a leak. Schema, medical decision logic, explicit time validation, unique original quote linkage, document coverage, max batch/body/total/token and one logical-call limits remain. Original 202 expected medical assertions are retained; fake input consumer was adapted to the carrier.

## Author evidence independently read

privacy-green.log/XML show 284 passed, 0 failure/error/skip, 4.841 seconds: original202 + new13 formal-wrapper + existing69 privacy/identity tests. Source manifest matches the reviewed extractor/test hashes. Reviewer did not rerun the suite.

- Green log SHA256 e594317c213fe2afcc9a6d770b137fe3ee3e11f268ed9c7e776f9bf80b06c057.
- Green XML a0dc758794d647ca8510898c8052dd4153af56f7bde1cde25e13c423f0029b85.
- Manifest 6d6d6ec1b1a39bb4d3e0db27d13f52d6666a425c7cc92dee951a68624d87e462.

All are in F:/MedQC-worktrees/qc-fix-critical-v2-20261008/.tmp/tc02-closure/. Original new13 red result 8 fail/5 pass is retained: seven address/unit/combined/two-document serialization failures, one invalid raw-time string blocked by the existing identity gate. Root classification accepted: the latter is metadata-contract coverage, not demonstrated leakage. Prior 202/83 failures remain separately recorded in fixed-219b-review.md/.json.

## Literal-marker boundary probe

Root authorized one finite pure stdlib capture, now finished and slot released. No env/PG/model/network or application imports. Exact helper, actual formal wrapper and exact stdlib shared time functions were used; helper relative imports alone were removed for isolated execution. Fixed unknown response is a capture fixture, not a medical answer.

Frozen expectation: preserve medical text, unique doc/span mapping, reject a wrong-document quote. Synthetic first body contained real-newline SPAN_BEGIN and SPAN_END for both d1:full and d2:full plus its own unique completed action; second body contained a distinct synthetic action. Both had valid normalized times. The actual delegate received valid metadata JSON and identical body/span view, preserving both actions. Ordered metadata plus body_char_count reconstructed each whole body, including embedded markers, and consumed the prompt exactly. Exact _parsed accepted each legitimate continuous quote and rejected the incorrect cross-document quote. No production source mix-up was proven.

The present test read_sent_documents function at lines119-134 checks marker counts across the entire prompt and splits at the first matching end marker. Each document's marker count was two instead of one, so its decoding contract fails on embedded marker text. This is a concrete auxiliary decoder/input-boundary gap; it is not proof that the production quote validator accepts another document's medical action. Recommended narrow next step is to specify ordered character-count consumption and freeze this same marker case. Do not ignore the document or change its medical expectation. Probe prompt SHA256 3dcc4f802767606ddc16e41979dcff83d15f7a7fcf7f08adbb588bf27ffe98dc.

## Pending final binding

Wait for root/owner fixed commit, verify tested hashes against final blobs and scoped paths, then issue integration conclusion. One git-status read failed with a work-tree error, so it was not treated as clean-state evidence; no Git mutation occurred. Real model/clinical semantics, existing normal C missing lab-ID exact-coordinate limitation and ambiguous clinical event/time boundaries remain open. No original patient material was accessed or included.

