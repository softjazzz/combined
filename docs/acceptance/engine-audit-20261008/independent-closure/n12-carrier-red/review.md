# N12 formal privacy carrier: independent impact check

**N12-PV01 confirmed: reopen the input carrier boundary subitem for LX0609-04-04-02 (N12), P1.** Fixed source `ce1d0771a1674073f3dbb4f019dfb2a4e40af1cc`. This does not undo independently accepted N12 semantic/state checks; the old 43 direct fake results do not cover this formal input boundary.

The actual call path is `execution.py:375` formal wrap -> resource client at 453 and surgery function at 468 -> `executor_registry.py:591-597` forwards the same resource client -> native N12 `2452-2455` -> `_typed_037_controlled_outcome:1097/1113/1116` builds VisitDocument and calls the extraction helper. The legacy dispatch also forwards the wrapped client at execution 808-812. Helper `134/136` redacts multiline body and builds spans; `150` JSON-serializes both; `155` invokes client.generate. Formal wrapper `llm_prompt_privacy.py:418-421` redacts the entire serialized prompt again. Parser line 160 still validates against the helper's earlier inputs.

Address/work-unit regex values at privacy lines 61/77 stop at real newline, not the serialized escaped newline. Consequently a second redaction crosses the original line boundary, removing the first medical phrase and changing span structure. Source blobs: helper `06f33a4a16de41a61cf903eeac863878dd4d2d9e`; wrapper `50968e90d7e8060df0166214ca4d021437f63045`. Full call-site bindings are indexed in [review.json](review.json).

## Frozen probe and actual result

One authorized standard-library run captured verbatim fixed N12 helper + formal privacy wrapper delegate input. Only original production `_document_spans`, `_usage` and `_located_present` functions were injected in place of the three relative dependency imports; there was no full application import. Inputs use existing N12 `_visits` pre/post medical bodies without changing a character, prefixed only with already synthetic TC02 address/unit/phone labels and real newline structure (including original fixed219b address fixture). Expected JSON validity, privacy removal, medical quote retention and identical direct/formal body/span views were frozen before execution.

| Prefix | Previsit | Postvisit |
|---|---|---|
| None | preserved | preserved |
| Phone | preserved | preserved |
| Current residence address | damaged | damaged |
| Work unit | damaged | damaged |
| Original 219b synthetic address | damaged | damaged |

**10 cases: 4 controls preserved, 6 confirmed carrier mismatches; zero support errors.** In each damaged previsit the existing `ASA II` level quote is removed; in each damaged postvisit the existing consciousness-clear quote is removed. Original span keys `d1:s1/s2/s3` collapse to `d1:s1`; transmitted body and spans differ from the helper view. All 10 transmitted JSON inputs still parse: this N12 evidence proves view/medical-content corruption, not invalid JSON. Synthetic private values are absent in all captures. Unknown fake response atoms deliberately assert no clinical judgment; helper ready states cannot certify the altered transport view.

Actual sent strings, parsed documents and both views are retained in [first-capture.json](first-capture.json); [first-run.log](first-run.log) preserves the first execution. Source and expectation hashes stayed unchanged. Twenty synthetic capture delegate calls (10 direct + 10 wrapped) used zero real models; guard denied env/private/DB/network/subprocess. The exclusive slot was immediately released. No production/shared tests or prior frozen expectation was changed.

## Closure boundary

N12 must send and validate one identical privacy-checked body/span view through the actual formal wrapper, retaining known-identity fail-closed checks and every original medical quote/coordinate. Preserve these frozen address/unit/newline cases and normal/phone controls, existing full-document absence/unknown and cross-document quotation contracts, and original call/token limits. Do not remove the wrapper or weaken an oracle for green. Engineering carrier closure remains separate from real-model and clinical-input verification. The original 43 direct fake results remain valid within their covered scope. They passed a client directly and cannot be cited as covering the formal wrapper boundary.
