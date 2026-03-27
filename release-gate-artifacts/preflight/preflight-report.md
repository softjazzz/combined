# MedQC Preflight Gate Report

- total steps: 5
- passed steps: 5
- failed steps: 0
- all passed: True

## Steps
- frontend_encoding: PASS (1.37s)
```text
> medical-qc-system@1.0.0 check:encoding D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web
> node scripts/check-encoding.mjs

encoding check passed (staged): 0 text file(s) scanned
```
- frontend_typecheck_release: PASS (4.5s)
```text
> medical-qc-system@1.0.0 type-check:release D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web
> tsc --noEmit -p tsconfig.release.json
```
- frontend_unit_tests_release: PASS (3.42s)
```text
> medical-qc-system@1.0.0 test:unit:release D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web
> vitest run --config vitest.release.config.mjs src/api/__tests__/qc.spec.ts src/api/__tests__/panel.spec.ts src/utils/__tests__/api-envelope.spec.ts


[1m[7m[36m RUN [39m[27m[22m [36mv2.1.9 [39m[90mD:/LLM/lx0222/health-qc-monorepo/apps/medqc-web[39m

 [32m✓[39m src/utils/__tests__/api-envelope.spec.ts [2m([22m[2m7 tests[22m[2m)[22m[90m 6[2mms[22m[39m
 [32m✓[39m src/api/__tests__/panel.spec.ts [2m([22m[2m3 tests[22m[2m)[22m[90m 6[2mms[22m[39m
 [32m✓[39m src/api/__tests__/qc.spec.ts [2m([22m[2m3 tests[22m[2m)[22m[90m 6[2mms[22m[39m

[2m Test Files [22m [1m[32m3 passed[39m[22m[90m (3)[39m
[2m      Tests [22m [1m[32m13 passed[39m[22m[90m (13)[39m
[2m   Start at [22m 11:13:11
[2m   Duration [22m 2.05s[2m (transform 139ms, setup 68ms, collect 155ms, tests 18ms, environment 2.75s, prepare 646ms)[22m
```
- frontend_build: PASS (42.26s)
```text
> medical-qc-system@1.0.0 build D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web
> vite build --config vite.config.mjs --configLoader native

[36mvite v6.3.5 [32mbuilding for production...[36m[39m
transforming...
[32m✓[39m 5358 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                                                                [39m[1m[2m    1.02 kB[22m[1m[22m[2m │ gzip:   0.52 kB[22m
[2mdist/[22m[32massets/png/lx-logo-DskHIQ7M.png                                           [39m[1m[2m    7.48 kB[22m[1m[22m
[2mdist/[22m[35massets/css/StatusTag-tn0RQdqM.css                                         [39m[1m[2m    0.00 kB[22m[1m[22m[2m │ gzip:   0.02 kB[22m
[2mdist/[22m[35massets/css/TestDemo-Dwjd_cTq.css                                          [39m[1m[2m    0.04 kB[22m[1m[22m[2m │ gzip:   0.06 kB[22m
[2mdist/[22m[35massets/css/RecordDetailView-B2_fpLeb.css                                  [39m[1m[2m    0.07 kB[22m[1m[22m[2m │ gzip:   0.09 kB[22m
[2mdist/[22m[35massets/css/BarChart-CKee6C8E.css                                          [39m[1m[2m    0.09 kB[22m[1m[22m[2m │ gzip:   0.09 kB[22m
[2mdist/[22m[35massets/css/LLMConfigTest-CefCTpSQ.css                                     [39m[1m[2m    0.15 kB[22m[1m[22m[2m │ gzip:   0.14 kB[22m
[2mdist/[22m[35massets/css/CodingRulesTab-CfvSISIG.css                                    [39m[1m[2m    0.15 kB[22m[1m[22m[2m │ gzip:   0.14 kB[22m
[2mdist/[22m[35massets/css/WorkstationRulesView-BK4Brdgb.css                              [39m[1m[2m    0.16 kB[22m[1m[22m[2m │ gzip:   0.14 kB[22m
[2mdist/[22m[35massets/css/RuleDocView-F_62sKZe.css                                       [39m[1m[2m    0.16 kB[22m[1m[22m[2m │ gzip:   0.12 kB[22m
[2mdist/[22m[35massets/css/Analysis-D04txbWc.css                                          [39m[1m[2m    0.18 kB[22m[1m[22m[2m │ gzip:   0.15 kB[22m
[2mdist/[22m[35massets/css/MyTasksView-D25z4A4X.css                                       [39m[1m[2m    0.22 kB[22m[1m[22m[2m │ gzip:   0.15 kB[22m
[2mdist/[22m[35massets/css/AllTasksView-COf9BKCt.css                                      [39m[1m[2m    0.22 kB[22m[1m[22m[2m │ gzip:   0.15 kB[22m
[2mdist/[22m[35massets/css/TestThreeColumn-gguUmvRj.css                                   [39m[1m[2m    0.23 kB[22m[1m[22m[2m │ gzip:   0.17 kB[22m
[2mdist/[22m[35massets/css/SimpleLLMTest-Dv4ZhnUA.css                                     [39m[1m[2m    0.23 kB[22m[1m[22m[2m │ gzip:   0.18 kB[22m
[2mdist/[22m[35massets/css/AppealList-BCjSzTLK.css                                        [39m[1m[2m    0.25 kB[22m[1m[22m[2m │ gzip:   0.17 kB[22m
[2mdist/[22m[35massets/css/MultiDocumentMergeTest-UtqLyvRq.css                            [39m[1m[2m    0.25 kB[22m[1m[22m[2m │ gzip:   0.18 kB[22m
[2mdist/[22m[35massets/css/StaffRankingView-ChHf7iVN.css                                  [39m[1m[2m    0.27 kB[22m[1m[22m[2m │ gzip:   0.19 kB[22m
[2mdist/[22m[35massets/css/LLMParseResultView-CIDsXOz7.css                                [39m[1m[2m    0.28 kB[22m[1m[22m[2m │ gzip:   0.19 kB[22m
[2mdist/[22m[35massets/css/RectificationList-B0cL57to.css                                 [39m[1m[2m    0.31 kB[22m[1m[22m[2m │ gzip:   0.19 kB[22m
[2mdist/[22m[35massets/css/MedicalRecordDetailSimple-BLvi8Tyc.css                         [39m[1m[2m    0.33 kB[22m[1m[22m[2m │ gzip:   0.18 kB[22m
[2mdist/[22m[35massets/css/TableSkeleton-DdGnXDV3.css                                     [39m[1m[2m    0.34 kB[22m[1m[22m[2m │ gzip:   0.17 kB[22m
[2mdist/[22m[35massets/css/PermissionsView-PCEXdRNr.css                                   [39m[1m[2m    0.38 kB[22m[1m[22m[2m │ gzip:   0.21 kB[22m
[2mdist/[22m[35massets/css/GrouperConfig-CHWmQtjY.css                                     [39m[1m[2m    0.41 kB[22m[1m[22m[2m │ gzip:   0.24 kB[22m
[2mdist/[22m[35massets/css/AIProfileDashboard-CBCw3WBN.css                                [39m[1m[2m    0.43 kB[22m[1m[22m[2m │ gzip:   0.17 kB[22m
[2mdist/[22m[35massets/css/PasswordStrength-Z_fgeCvI.css                                  [39m[1m[2m    0.45 kB[22m[1m[22m[2m │ gzip:   0.25 kB[22m
[2mdist/[22m[35massets/css/MonitorDashboard-B3kSwFAK.css                                  [39m[1m[2m    0.51 kB[22m[1m[22m[2m │ gzip:   0.26 kB[22m
[2mdist/[22m[35massets/css/StatisticsView-DSsk0-EC.css                                    [39m[1m[2m    0.57 kB[22m[1m[22m[2m │ gzip:   0.33 kB[22m
[2mdist/[22m[35massets/css/DepartmentConfig-BIVsD7z_.css                                  [39m[1m[2m    0.65 kB[22m[1m[22m[2m │ gzip:   0.28 kB[22m
[2mdist/[22m[35massets/css/NotFoundView-CRDlZOuo.css                                      [39m[1m[2m    0.68 kB[22m[1m[22m[2m │ gzip:   0.39 kB[22m
[2mdist/[22m[35massets/css/ClassificationVersionTest-D4PQWJRW.css                         [39m[1m[2m    0.75 kB[22m[1m[22m[2m │ gzip:   0.37 kB[22m
[2mdist/[22m[35massets/css/Toolbar-5TT8b3x7.css                                           [39m[1m[2m    0.86 kB[22m[1m[22m[2m │ gzip:   0.37 kB[22m
[2mdist/[22m[35massets/css/FrontPageDemoView-CccE2RNV.css                                 [39m[1m[2m    0.88 kB[22m[1m[22m[2m │ gzip:   0.38 kB[22m
[2mdist/[22m[35massets/css/DipGrouperView-hb6LfE9j.css                                    [39m[1m[2m    1.01 kB[22m[1m[22m[2m │ gzip:   0.44 kB[22m
[2mdist/[22m[35massets/css/TestMedicalRecordsView-PaNa2FKg.css                            [39m[1m[2m    1.02 kB[22m[1m[22m[2m │ gzip:   0.40 kB[22m
[2mdist/[22m[35massets/css/DepartmentConfigTest-DiWysKY1.css                              [39m[1m[2m    1.03 kB[22m[1m[22m[2m │ gzip:   0.40 kB[22m
[2mdist/[22m[35massets/css/LLMApiConfigDatabase-CjP-BCVn.css                              [39m[1m[2m    1.06 kB[22m[1m[22m[2m │ gzip:   0.47 kB[22m
[2mdist/[22m[35massets/css/WorkstationV3View-hvwgGvwV.css                                 [39m[1m[2m    1.06 kB[22m[1m[22m[2m │ gzip:   0.39 kB[22m
[2mdist/[22m[35massets/css/ApiTestView-DU6JY0VF.css                                       [39m[1m[2m    1.14 kB[22m[1m[22m[2m │ gzip:   0.43 kB[22m
[2mdist/[22m[35massets/css/ApiTestView-CMeize9J.css                                       [39m[1m[2m    1.15 kB[22m[1m[22m[2m │ gzip:   0.42 kB[22m
[2mdist/[22m[35massets/css/AnalyticsView-ChBLX_iU.css                                     [39m[1m[2m    1.16 kB[22m[1m[22m[2m │ gzip:   0.42 kB[22m
[2mdist/[22m[35massets/css/BatchProcessorTest-Dcp5fHnx.css                                [39m[1m[2m    1.16 kB[22m[1m[22m[2m │ gzip:   0.46 kB[22m
[2mdist/[22m[35massets/css/MainLayout-CIDZijdH.css                                        [39m[1m[2m    1.22 kB[22m[1m[22m[2m │ gzip:   0.43 kB[22m
[2mdist/[22m[35massets/css/SichuanQCDemo-BZPeipvA.css                                     [39m[1m[2m    1.23 kB[22m[1m[22m[2m │ gzip:   0.47 kB[22m
[2mdist/[22m[35massets/css/MultiFileUploadTest-CtYhKXt2.css                               [39m[1m[2m    1.26 kB[22m[1m[22m[2m │ gzip:   0.50 kB[22m
[2mdist/[22m[35massets/css/RunningRecordsViewNew-B0LEtmxh.css                             [39m[1m[2m    1.35 kB[22m[1m[22m[2m │ gzip:   0.51 kB[22m
[2mdist/[22m[35massets/css/SimpleLayout-C2YNjAUT.css                                      [39m[1m[2m    1.37 kB[22m[1m[22m[2m │ gzip:   0.63 kB[22m
[2mdist/[22m[35massets/css/FinalRecordsView-HLWZrdKc.css                                  [39m[1m[2m    1.42 kB[22m[1m[22m[2m │ gzip:   0.48 kB[22m
[2mdist/[22m[35massets/css/DataImportView-DfyuFE-6.css                                    [39m[1m[2m    1.43 kB[22m[1m[22m[2m │ gzip:   0.50 kB[22m
[2mdist/[22m[35massets/css/ViolationsList-L95j0_0O.css                                    [39m[1m[2m    1.67 kB[22m[1m[22m[2m │ gzip:   0.45 kB[22m
[2mdist/[22m[35massets/css/QCIntegrationTest-14pzTxes.css                                 [39m[1m[2m    1.81 kB[22m[1m[22m[2m │ gzip:   0.59 kB[22m
[2mdist/[22m[35massets/css/LayoutShell-CZNIojrc.css                                       [39m[1m[2m    1.84 kB[22m[1m[22m[2m │ gzip:   0.53 kB[22m
[2mdist/[22m[35massets/css/SmartImportSimple-CHFAoeA9.css                                 [39m[1m[2m    2.00 kB[22m[1m[22m[2m │ gzip:   0.58 kB[22m
[2mdist/[22m[35massets/css/SichuanQCView-BZpV5MXx.css                                     [39m[1m[2m    2.01 kB[22m[1m[22m[2m │ gzip:   0.62 kB[22m
[2mdist/[22m[35massets/css/ForgotPasswordView-mMPCJIHN.css                                [39m[1m[2m    2.14 kB[22m[1m[22m[2m │ gzip:   0.77 kB[22m
[2mdist/[22m[35massets/css/CustomRulesManager-DlovqmZl.css                                [39m[1m[2m    2.15 kB[22m[1m[22m[2m │ gzip:   0.72 kB[22m
[2mdist/[22m[35massets/css/ThreeColumnValidation-DEb2IQ1f.css                             [39m[1m[2m    2.30 kB[22m[1m[22m[2m │ gzip:   0.74 kB[22m
[2mdist/[22m[35massets/css/ContextAside-D4W0049v.css                                      [39m[1m[2m    2.42 kB[22m[1m[22m[2m │ gzip:   0.70 kB[22m
[2mdist/[22m[35massets/css/EMRViewer-TQ4acMBg.css                                         [39m[1m[2m    2.48 kB[22m[1m[22m[2m │ gzip:   0.84 kB[22m
[2mdist/[22m[35massets/css/WorkstationLayout-DoHozdYG.css                                 [39m[1m[2m    2.52 kB[22m[1m[22m[2m │ gzip:   0.64 kB[22m
[2mdist/[22m[35massets/css/DrgGrouperView-DZ6uRiQL.css                                    [39m[1m[2m    2.53 kB[22m[1m[22m[2m │ gzip:   0.81 kB[22m
[2mdist/[22m[35massets/css/LLMQCDemo-CKhDpiMW.css                                         [39m[1m[2m    2.53 kB[22m[1m[22m[2m │ gzip:   0.76 kB[22m
[2mdist/[22m[35massets/css/NavTree-DWqdLPPV.css                                           [39m[1m[2m    2.70 kB[22m[1m[22m[2m │ gzip:   0.66 kB[22m
[2mdist/[22m[35massets/css/QCStatsView-CoT-cCis.css                                       [39m[1m[2m    2.80 kB[22m[1m[22m[2m │ gzip:   0.81 kB[22m
[2mdist/[22m[35massets/css/BatchFileProcessor-Cz90rH87.css                                [39m[1m[2m    2.84 kB[22m[1m[22m[2m │ gzip:   0.87 kB[22m
[2mdist/[22m[35massets/css/vendor-antd-CqAJlDPB.css                                       [39m[1m[2m    2.93 kB[22m[1m[22m[2m │ gzip:   1.17 kB[22m
[2mdist/[22m[35massets/css/CodingAssistant-DNezJNeq.css                                   [39m[1m[2m    3.01 kB[22m[1m[22m[2m │ gzip:   0.75 kB[22m
[2mdist/[22m[35massets/css/QCReviewDrawer-iOqMV7ae.css                                    [39m[1m[2m    3.07 kB[22m[1m[22m[2m │ gzip:   0.75 kB[22m
[2mdist/[22m[35massets/css/QCOverviewView-CzcvQjA6.css                                    [39m[1m[2m    3.33 kB[22m[1m[22m[2m │ gzip:   0.92 kB[22m
[2mdist/[22m[35massets/css/BatchSmartImportView-DxfrDKJM.css                              [39m[1m[2m    3.51 kB[22m[1m[22m[2m │ gzip:   1.04 kB[22m
[2mdist/[22m[35massets/css/CnDrgGrouperView-8nvei37b.css                                  [39m[1m[2m    3.54 kB[22m[1m[22m[2m │ gzip:   0.91 kB[22m
[2mdist/[22m[35massets/css/FeedbacksView-DSkllTMn.css                                     [39m[1m[2m    3.67 kB[22m[1m[22m[2m │ gzip:   0.91 kB[22m
[2mdist/[22m[35massets/css/RegisterView-CXEbS6UQ.css                                      [39m[1m[2m    3.69 kB[22m[1m[22m[2m │ gzip:   0.98 kB[22m
[2mdist/[22m[35massets/css/EnhancedLogPanel-tB3eOnUR.css                                  [39m[1m[2m    3.75 kB[22m[1m[22m[2m │ gzip:   1.08 kB[22m
[2mdist/[22m[35massets/css/DashboardView-B3vn47ta.css                                     [39m[1m[2m    3.79 kB[22m[1m[22m[2m │ gzip:   1.13 kB[22m
[2mdist/[22m[35massets/css/SettlementForm-BSy-GD6A.css                                    [39m[1m[2m    3.95 kB[22m[1m[22m[2m │ gzip:   1.05 kB[22m
[2mdist/[22m[35massets/css/ModalTest-zk31bCzN.css                                         [39m[1m[2m    4.44 kB[22m[1m[22m[2m │ gzip:   1.24 kB[22m
[2mdist/[22m[35massets/css/QCAnalysisDemoPanel-CxuAaZDx.css                               [39m[1m[2m    4.55 kB[22m[1m[22m[2m │ gzip:   0.92 kB[22m
[2mdist/[22m[35massets/css/QualityControlPointManagement-4tOCG_DH.css                     [39m[1m[2m    4.64 kB[22m[1m[22m[2m │ gzip:   0.83 kB[22m
[2mdist/[22m[35massets/css/LoginView-B52NzceC.css                                         [39m[1m[2m    4.76 kB[22m[1m[22m[2m │ gzip:   1.05 kB[22m
[2mdist/[22m[35massets/css/LX33CreateRuleView-DAMBwdUl.css                                [39m[1m[2m    4.85 kB[22m[1m[22m[2m │ gzip:   1.08 kB[22m
[2mdist/[22m[35massets/css/EditMedicalRecord-DJrNSa5c.css                                 [39m[1m[2m    4.85 kB[22m[1m[22m[2m │ gzip:   1.12 kB[22m
[2mdist/[22m[35massets/css/ExamplesModal-DPPFiNYS.css                                     [39m[1m[2m    4.93 kB[22m[1m[22m[2m │ gzip:   1.10 kB[22m
[2mdist/[22m[35massets/css/MedicalRecordDetail-xDWwJxqO.css                               [39m[1m[2m    4.93 kB[22m[1m[22m[2m │ gzip:   1.29 kB[22m
[2mdist/[22m[35massets/css/QualityControlPointCreate-BJXvUEjm.css                         [39m[1m[2m    5.04 kB[22m[1m[22m[2m │ gzip:   0.86 kB[22m
[2mdist/[22m[35massets/css/LLMResultModal-Cyw57_r7.css                                    [39m[1m[2m    5.23 kB[22m[1m[22m[2m │ gzip:   1.13 kB[22m
[2mdist/[22m[35massets/css/DRGGroupingTab-DwnyLFQh.css                                    [39m[1m[2m    5.57 kB[22m[1m[22m[2m │ gzip:   1.44 kB[22m
[2mdist/[22m[35massets/css/CodingDetail-DUeUR-4P.css                                      [39m[1m[2m    5.60 kB[22m[1m[22m[2m │ gzip:   1.31 kB[22m
[2mdist/[22m[35massets/css/Index-BsTB2EaE.css                                             [39m[1m[2m    5.61 kB[22m[1m[22m[2m │ gzip:   1.28 kB[22m
[2mdist/[22m[35massets/css/DataSyncConfigPage-0KGF4P4h.css                                [39m[1m[2m    5.64 kB[22m[1m[22m[2m │ gzip:   1.59 kB[22m
[2mdist/[22m[35massets/css/ProfileView-BQjc8BbO.css                                       [39m[1m[2m    5.71 kB[22m[1m[22m[2m │ gzip:   1.29 kB[22m
[2mdist/[22m[35massets/css/GroupingPredict-BDYLHzLn.css                                   [39m[1m[2m    6.21 kB[22m[1m[22m[2m │ gzip:   1.43 kB[22m
[2mdist/[22m[35massets/css/FeeMonitoring-qkKcSch9.css                                     [39m[1m[2m    6.21 kB[22m[1m[22m[2m │ gzip:   1.42 kB[22m
[2mdist/[22m[35massets/css/SemanticRulesView-C5b2X9Ve.css                                 [39m[1m[2m    6.58 kB[22m[1m[22m[2m │ gzip:   1.66 kB[22m
[2mdist/[22m[35massets/css/QCRulesDemoPanel-Cvrgrqvf.css                                  [39m[1m[2m    6.63 kB[22m[1m[22m[2m │ gzip:   1.18 kB[22m
[2mdist/[22m[35massets/css/MedicalRecordsView-De3BHy_B.css                                [39m[1m[2m    7.09 kB[22m[1m[22m[2m │ gzip:   1.57 kB[22m
[2mdist/[22m[35massets/css/RulesView-BgND_trg.css                                         [39m[1m[2m    7.11 kB[22m[1m[22m[2m │ gzip:   1.76 kB[22m
[2mdist/[22m[35massets/css/CreateMedicalRecord-Covk0L8U.css                               [39m[1m[2m    7.18 kB[22m[1m[22m[2m │ gzip:   1.46 kB[22m
[2mdist/[22m[35massets/css/WorkstationV2View-DjpmGpW8.css                                 [39m[1m[2m    8.41 kB[22m[1m[22m[2m │ gzip:   2.07 kB[22m
[2mdist/[22m[35massets/css/CDMDataView-CTMIoe30.css                                       [39m[1m[2m    8.54 kB[22m[1m[22m[2m │ gzip:   1.94 kB[22m
[2mdist/[22m[35massets/css/LLMApiConfig-BafSxMOd.css                                      [39m[1m[2m   10.31 kB[22m[1m[22m[2m │ gzip:   1.91 kB[22m
[2mdist/[22m[35massets/css/LLMQCDemoEnhanced-BE68MJqh.css                                 [39m[1m[2m   10.81 kB[22m[1m[22m[2m │ gzip:   2.22 kB[22m
[2mdist/[22m[35massets/css/PreAnalysisView-CG36NBnM.css                                   [39m[1m[2m   12.94 kB[22m[1m[22m[2m │ gzip:   2.79 kB[22m
[2mdist/[22m[35massets/css/LLMQCDemoEnhancedNew-BEPACrGM.css                              [39m[1m[2m   14.98 kB[22m[1m[22m[2m │ gzip:   2.65 kB[22m
[2mdist/[22m[35massets/css/SmartImportMedicalRecord-QvEDU6zn.css                          [39m[1m[2m   15.36 kB[22m[1m[22m[2m │ gzip:   2.63 kB[22m
[2mdist/[22m[35massets/css/SettingsView-ByboVT7P.css                                      [39m[1m[2m   19.66 kB[22m[1m[22m[2m │ gzip:   4.07 kB[22m
[2mdist/[22m[35massets/css/LX33DemoView-Xz5Egb_v.css                                      [39m[1m[2m   23.70 kB[22m[1m[22m[2m │ gzip:   3.15 kB[22m
[2mdist/[22m[35massets/css/ClinicalWorkstationDemoView-CBmqMGyK.css                       [39m[1m[2m   25.77 kB[22m[1m[22m[2m │ gzip:   3.67 kB[22m
[2mdist/[22m[35massets/css/MedicalRecordDetail-D7NQbi-a.css                               [39m[1m[2m   31.39 kB[22m[1m[22m[2m │ gzip:   5.99 kB[22m
[2mdist/[22m[35massets/css/WorkstationV4View-DQa4I87Z.css                                 [39m[1m[2m   50.04 kB[22m[1m[22m[2m │ gzip:   8.44 kB[22m
[2mdist/[22m[35massets/css/BatchRuleTest-BQx60t_M.css                                     [39m[1m[2m   57.67 kB[22m[1m[22m[2m │ gzip:   7.24 kB[22m
[2mdist/[22m[35massets/css/index-DsIFbOCq.css                                             [39m[1m[2m  252.70 kB[22m[1m[22m[2m │ gzip:  30.30 kB[22m
[2mdist/[22m[36massets/js/_plugin-vue_export-helper-DlAUqK2U.js                           [39m[1m[2m    0.09 kB[22m[1m[22m[2m │ gzip:   0.10 kB[22m
[2mdist/[22m[36massets/js/auth-B-EunM_f.js                                                [39m[1m[2m    0.12 kB[22m[1m[22m[2m │ gzip:   0.13 kB[22m
[2mdist/[22m[36massets/js/api-helpers-C8vY1ZOw.js                                         [39m[1m[2m    0.44 kB[22m[1m[22m[2m │ gzip:   0.29 kB[22m
[2mdist/[22m[36massets/js/api-envelope-CAng04Kn.js                                        [39m[1m[2m    0.53 kB[22m[1m[22m[2m │ gzip:   0.29 kB[22m
[2mdist/[22m[36massets/js/llmParse-CcrGGTc7.js                                            [39m[1m[2m    0.57 kB[22m[1m[22m[2m │ gzip:   0.30 kB[22m
[2mdist/[22m[36massets/js/SimpleLayout-CJcbD6OL.js                                        [39m[1m[2m    0.78 kB[22m[1m[22m[2m │ gzip:   0.51 kB[22m
[2mdist/[22m[36massets/js/auth-token-JYsLsdiL.js                                          [39m[1m[2m    0.96 kB[22m[1m[22m[2m │ gzip:   0.30 kB[22m
[2mdist/[22m[36massets/js/TableSkeleton-CkVwgXSu.js                                       [39m[1m[2m    1.03 kB[22m[1m[22m[2m │ gzip:   0.55 kB[22m
[2mdist/[22m[36massets/js/StatusTag-C2SzM0SY.js                                           [39m[1m[2m    1.05 kB[22m[1m[22m[2m │ gzip:   0.49 kB[22m
[2mdist/[22m[36massets/js/medicalDocumentApi-DX9dfkTO.js                                  [39m[1m[2m    1.09 kB[22m[1m[22m[2m │ gzip:   0.57 kB[22m
[2mdist/[22m[36massets/js/frontpage-CwoF3gfH.js                                           [39m[1m[2m    1.17 kB[22m[1m[22m[2m │ gzip:   0.54 kB[22m
[2mdist/[22m[36massets/js/TestDemo-DmGbiSzg.js                                            [39m[1m[2m    1.49 kB[22m[1m[22m[2m │ gzip:   0.94 kB[22m
[2mdist/[22m[36massets/js/ICDCodeSearch.vue_vue_type_script_setup_true_lang-CPRhYv4o.js   [39m[1m[2m    1.80 kB[22m[1m[22m[2m │ gzip:   1.05 kB[22m
[2mdist/[22m[36massets/js/drg-Dxr4zjv3.js                                                 [39m[1m[2m    1.85 kB[22m[1m[22m[2m │ gzip:   1.08 kB[22m
[2mdist/[22m[36massets/js/tasks-Ctkhj5b3.js                                               [39m[1m[2m    1.86 kB[22m[1m[22m[2m │ gzip:   0.94 kB[22m
[2mdist/[22m[36massets/js/suggestionFormatter-Bay2MeaF.js                                 [39m[1m[2m    1.87 kB[22m[1m[22m[2m │ gzip:   0.93 kB[22m
[2mdist/[22m[36massets/js/RuleDocView-goJifcwa.js                                         [39m[1m[2m    2.07 kB[22m[1m[22m[2m │ gzip:   1.14 kB[22m
[2mdist/[22m[36massets/js/BatchProcessorTest-CNlzssEZ.js                                  [39m[1m[2m    2.19 kB[22m[1m[22m[2m │ gzip:   1.24 kB[22m
[2mdist/[22m[36massets/js/NotFoundView-BNCf6nfH.js                                        [39m[1m[2m    2.65 kB[22m[1m[22m[2m │ gzip:   1.25 kB[22m
[2mdist/[22m[36massets/js/useDRGGrouping-DxmZbLMW.js                                      [39m[1m[2m    2.68 kB[22m[1m[22m[2m │ gzip:   1.49 kB[22m
[2mdist/[22m[36massets/js/dipGrouper-Bn6MeVAX.js                                          [39m[1m[2m    2.79 kB[22m[1m[22m[2m │ gzip:   1.21 kB[22m
[2mdist/[22m[36massets/js/defects-DsItGHTl.js                                             [39m[1m[2m    2.94 kB[22m[1m[22m[2m │ gzip:   1.33 kB[22m
[2mdist/[22m[36massets/js/NavTree-DEgBSFu7.js                                             [39m[1m[2m    3.05 kB[22m[1m[22m[2m │ gzip:   1.60 kB[22m
[2mdist/[22m[36massets/js/LLMConfigTest-DNc4-QSp.js                                       [39m[1m[2m    3.16 kB[22m[1m[22m[2m │ gzip:   1.36 kB[22m
[2mdist/[22m[36massets/js/PasswordStrength-BYoT9atJ.js                                    [39m[1m[2m    3.37 kB[22m[1m[22m[2m │ gzip:   1.56 kB[22m
[2mdist/[22m[36massets/js/ruleDocumentMapping-CBlIOtBp.js                                 [39m[1m[2m    3.53 kB[22m[1m[22m[2m │ gzip:   1.43 kB[22m
[2mdist/[22m[36massets/js/RecordDetailView-DPi7NGui.js                                    [39m[1m[2m    3.67 kB[22m[1m[22m[2m │ gzip:   1.82 kB[22m
[2mdist/[22m[36massets/js/TestThreeColumn-Ble8bZ9t.js                                     [39m[1m[2m    3.67 kB[22m[1m[22m[2m │ gzip:   1.62 kB[22m
[2mdist/[22m[36massets/js/MedicalRecordDetailSimple-mHj9VSar.js                           [39m[1m[2m    4.10 kB[22m[1m[22m[2m │ gzip:   1.86 kB[22m
[2mdist/[22m[36massets/js/mock-icd-codes-B-0CLI8f.js                                      [39m[1m[2m    4.10 kB[22m[1m[22m[2m │ gzip:   1.58 kB[22m
[2mdist/[22m[36massets/js/LayoutShell-BXXHYtcZ.js                                         [39m[1m[2m    4.19 kB[22m[1m[22m[2m │ gzip:   1.67 kB[22m
[2mdist/[22m[36massets/js/drgGrouper-ChRgZgfz.js                                          [39m[1m[2m    4.27 kB[22m[1m[22m[2m │ gzip:   2.30 kB[22m
[2mdist/[22m[36massets/js/documentTypeUtils-DuzhYEk0.js                                   [39m[1m[2m    4.29 kB[22m[1m[22m[2m │ gzip:   1.40 kB[22m
[2mdist/[22m[36massets/js/export-B1noKaEN.js                                              [39m[1m[2m    4.47 kB[22m[1m[22m[2m │ gzip:   1.89 kB[22m
[2mdist/[22m[36massets/js/MultiFileUploadTest-Co3FUjK6.js                                 [39m[1m[2m    4.74 kB[22m[1m[22m[2m │ gzip:   2.35 kB[22m
[2mdist/[22m[36massets/js/GrouperTabsView-DwITdpjP.js                                     [39m[1m[2m    4.78 kB[22m[1m[22m[2m │ gzip:   1.90 kB[22m
[2mdist/[22m[36massets/js/auth-C_TQq42R.js                                                [39m[1m[2m    4.89 kB[22m[1m[22m[2m │ gzip:   1.75 kB[22m
[2mdist/[22m[36massets/js/QCStatsView-q73lpaRZ.js                                         [39m[1m[2m    5.01 kB[22m[1m[22m[2m │ gzip:   2.17 kB[22m
[2mdist/[22m[36massets/js/StaffRankingView-BJ0PxRJs.js                                    [39m[1m[2m    5.41 kB[22m[1m[22m[2m │ gzip:   2.22 kB[22m
[2mdist/[22m[36massets/js/api-C6DI-kMd.js                                                 [39m[1m[2m    5.55 kB[22m[1m[22m[2m │ gzip:   2.54 kB[22m
[2mdist/[22m[36massets/js/error-handler-CE7Uc3il.js                                       [39m[1m[2m    5.67 kB[22m[1m[22m[2m │ gzip:   2.47 kB[22m
[2mdist/[22m[36massets/js/initLLMDatabase-l0-RyN2j.js                                     [39m[1m[2m    5.67 kB[22m[1m[22m[2m │ gzip:   2.15 kB[22m
[2mdist/[22m[36massets/js/BarChart-CBUq7YvO.js                                            [39m[1m[2m    5.68 kB[22m[1m[22m[2m │ gzip:   1.96 kB[22m
[2mdist/[22m[36massets/js/ContextAside-BBoLK-80.js                                        [39m[1m[2m    5.72 kB[22m[1m[22m[2m │ gzip:   2.33 kB[22m
[2mdist/[22m[36massets/js/LLMParseResultView-vlAr85-B.js                                  [39m[1m[2m    5.82 kB[22m[1m[22m[2m │ gzip:   2.92 kB[22m
[2mdist/[22m[36massets/js/CodingAssistant-BsVr3-Wd.js                                     [39m[1m[2m    5.98 kB[22m[1m[22m[2m │ gzip:   2.46 kB[22m
[2mdist/[22m[36massets/js/Toolbar-BVMPVQdv.js                                             [39m[1m[2m    6.19 kB[22m[1m[22m[2m │ gzip:   2.66 kB[22m
[2mdist/[22m[36massets/js/Index-Bw5LHk5t.js                                               [39m[1m[2m    6.58 kB[22m[1m[22m[2m │ gzip:   2.91 kB[22m
[2mdist/[22m[36massets/js/QualityControlPointManagement-BIhnQ-lN.js                       [39m[1m[2m    6.64 kB[22m[1m[22m[2m │ gzip:   2.35 kB[22m
[2mdist/[22m[36massets/js/QualityControlPointCreate-D0E2bZ9k.js                           [39m[1m[2m    6.72 kB[22m[1m[22m[2m │ gzip:   2.25 kB[22m
[2mdist/[22m[36massets/js/MultiDocumentMergeTest-_eYL6s3v.js                              [39m[1m[2m    6.89 kB[22m[1m[22m[2m │ gzip:   3.24 kB[22m
[2mdist/[22m[36massets/js/ThreeColumnValidation-CTmHy4Hk.js                               [39m[1m[2m    7.07 kB[22m[1m[22m[2m │ gzip:   2.60 kB[22m
[2mdist/[22m[36massets/js/SimpleLLMTest-C7YAChlc.js                                       [39m[1m[2m    7.36 kB[22m[1m[22m[2m │ gzip:   2.84 kB[22m
[2mdist/[22m[36massets/js/ScoringConfigView-CYbb7vfr.js                                   [39m[1m[2m    7.92 kB[22m[1m[22m[2m │ gzip:   3.13 kB[22m
[2mdist/[22m[36massets/js/CodingDetail-Bi8j4gZL.js                                        [39m[1m[2m    7.94 kB[22m[1m[22m[2m │ gzip:   3.48 kB[22m
[2mdist/[22m[36massets/js/LX33CreateRuleView-B5CwMmBG.js                                  [39m[1m[2m    8.02 kB[22m[1m[22m[2m │ gzip:   3.37 kB[22m
[2mdist/[22m[36massets/js/QCOverviewView-USbK7Q1p.js                                      [39m[1m[2m    8.20 kB[22m[1m[22m[2m │ gzip:   3.82 kB[22m
[2mdist/[22m[36massets/js/QCIntegrationTest-2u6xuo18.js                                   [39m[1m[2m    8.39 kB[22m[1m[22m[2m │ gzip:   3.75 kB[22m
[2mdist/[22m[36massets/js/ViolationsList-CqV4tdtF.js                                      [39m[1m[2m    8.48 kB[22m[1m[22m[2m │ gzip:   3.27 kB[22m
[2mdist/[22m[36massets/js/ExamplesModal-BvCThd_8.js                                       [39m[1m[2m    8.63 kB[22m[1m[22m[2m │ gzip:   3.15 kB[22m
[2mdist/[22m[36massets/js/EMRViewer-CR4i1UUN.js                                           [39m[1m[2m    8.88 kB[22m[1m[22m[2m │ gzip:   4.20 kB[22m
[2mdist/[22m[36massets/js/ForgotPasswordView-TTOa3yV7.js                                  [39m[1m[2m    8.98 kB[22m[1m[22m[2m │ gzip:   3.66 kB[22m
[2mdist/[22m[36massets/js/DepartmentConfigTest-DJYoiN9p.js                                [39m[1m[2m    9.12 kB[22m[1m[22m[2m │ gzip:   3.68 kB[22m
[2mdist/[22m[36massets/js/MonitorDashboard-DKqomJjo.js                                    [39m[1m[2m    9.14 kB[22m[1m[22m[2m │ gzip:   3.43 kB[22m
[2mdist/[22m[36massets/js/NotificationsView-Bz1UM5D_.js                                   [39m[1m[2m    9.18 kB[22m[1m[22m[2m │ gzip:   3.49 kB[22m
[2mdist/[22m[36massets/js/AppealList-8eYK1DpM.js                                          [39m[1m[2m    9.68 kB[22m[1m[22m[2m │ gzip:   4.02 kB[22m
[2mdist/[22m[36massets/js/ClassificationVersionTest-DKusYY-p.js                           [39m[1m[2m    9.69 kB[22m[1m[22m[2m │ gzip:   3.49 kB[22m
[2mdist/[22m[36massets/js/ApiTestView-Cryy_DIa.js                                         [39m[1m[2m   10.19 kB[22m[1m[22m[2m │ gzip:   4.19 kB[22m
[2mdist/[22m[36massets/js/ScoringRulesView-l31QXWkJ.js                                    [39m[1m[2m   10.45 kB[22m[1m[22m[2m │ gzip:   4.22 kB[22m
[2mdist/[22m[36massets/js/DataImportView-3TeKYTTM.js                                      [39m[1m[2m   10.69 kB[22m[1m[22m[2m │ gzip:   4.32 kB[22m
[2mdist/[22m[36massets/js/BatchSmartImportView-CuycSNlB.js                                [39m[1m[2m   10.83 kB[22m[1m[22m[2m │ gzip:   4.47 kB[22m
[2mdist/[22m[36massets/js/LLMResultModal-CFfxy-GD.js                                      [39m[1m[2m   10.94 kB[22m[1m[22m[2m │ gzip:   4.22 kB[22m
[2mdist/[22m[36massets/js/BatchFileProcessor-Otb4JFdH.js                                  [39m[1m[2m   10.95 kB[22m[1m[22m[2m │ gzip:   4.64 kB[22m
[2mdist/[22m[36massets/js/GrouperConfig-Db35YcX0.js                                       [39m[1m[2m   11.18 kB[22m[1m[22m[2m │ gzip:   4.09 kB[22m
[2mdist/[22m[36massets/js/DepartmentConfig-DqO8wugH.js                                    [39m[1m[2m   11.19 kB[22m[1m[22m[2m │ gzip:   3.86 kB[22m
[2mdist/[22m[36massets/js/GroupingPredict-sGJE_urA.js                                     [39m[1m[2m   11.47 kB[22m[1m[22m[2m │ gzip:   4.33 kB[22m
[2mdist/[22m[36massets/js/LLMApiConfigDatabase-DU8om0-f.js                                [39m[1m[2m   12.22 kB[22m[1m[22m[2m │ gzip:   4.55 kB[22m
[2mdist/[22m[36massets/js/WorkstationLayout-DuHFthgX.js                                   [39m[1m[2m   12.37 kB[22m[1m[22m[2m │ gzip:   4.38 kB[22m
[2mdist/[22m[36massets/js/EnhancedLogPanel-Crorr_Jq.js                                    [39m[1m[2m   12.45 kB[22m[1m[22m[2m │ gzip:   4.24 kB[22m
[2mdist/[22m[36massets/js/MyTasksView-CTOSCWQN.js                                         [39m[1m[2m   12.54 kB[22m[1m[22m[2m │ gzip:   4.33 kB[22m
[2mdist/[22m[36massets/js/CDMDataView-D8vfn79J.js                                         [39m[1m[2m   12.60 kB[22m[1m[22m[2m │ gzip:   4.70 kB[22m
[2mdist/[22m[36massets/js/QCRulesDemoPanel-ak8wLMAg.js                                    [39m[1m[2m   12.64 kB[22m[1m[22m[2m │ gzip:   4.99 kB[22m
[2mdist/[22m[36massets/js/testCases-BYW5TKzO.js                                           [39m[1m[2m   12.70 kB[22m[1m[22m[2m │ gzip:   5.68 kB[22m
[2mdist/[22m[36massets/js/WorkstationLoginView-BqV7GLQJ.js                                [39m[1m[2m   12.75 kB[22m[1m[22m[2m │ gzip:   4.81 kB[22m
[2mdist/[22m[36massets/js/MainLayout-DxZXKexp.js                                          [39m[1m[2m   12.82 kB[22m[1m[22m[2m │ gzip:   4.42 kB[22m
[2mdist/[22m[36massets/js/ModalTest-Coau20c6.js                                           [39m[1m[2m   13.07 kB[22m[1m[22m[2m │ gzip:   4.96 kB[22m
[2mdist/[22m[36massets/js/RectificationList-DmebA5Lv.js                                   [39m[1m[2m   13.73 kB[22m[1m[22m[2m │ gzip:   5.07 kB[22m
[2mdist/[22m[36massets/js/FeedbacksView-Cl1WMs_s.js                                       [39m[1m[2m   14.40 kB[22m[1m[22m[2m │ gzip:   4.75 kB[22m
[2mdist/[22m[36massets/js/PermissionsView-CVeEk-Wh.js                                     [39m[1m[2m   14.40 kB[22m[1m[22m[2m │ gzip:   4.52 kB[22m
[2mdist/[22m[36massets/js/DipGrouperView-lRcAbQkT.js                                      [39m[1m[2m   14.71 kB[22m[1m[22m[2m │ gzip:   4.45 kB[22m
[2mdist/[22m[36massets/js/apiService-BOo-iNmF.js                                          [39m[1m[2m   15.69 kB[22m[1m[22m[2m │ gzip:   3.91 kB[22m
[2mdist/[22m[36massets/js/FinalRecordsView-BNq56Yt0.js                                    [39m[1m[2m   15.99 kB[22m[1m[22m[2m │ gzip:   5.24 kB[22m
[2mdist/[22m[36massets/js/LoginView-BZimm77D.js                                           [39m[1m[2m   16.01 kB[22m[1m[22m[2m │ gzip:   5.42 kB[22m
[2mdist/[22m[36massets/js/RegisterView-DcnzK8w_.js                                        [39m[1m[2m   16.34 kB[22m[1m[22m[2m │ gzip:   5.84 kB[22m
[2mdist/[22m[36massets/js/StatisticsView-B3cqD4wp.js                                      [39m[1m[2m   16.60 kB[22m[1m[22m[2m │ gzip:   6.07 kB[22m
[2mdist/[22m[36massets/js/CreateMedicalRecord-QfaTb72s.js                                 [39m[1m[2m   17.01 kB[22m[1m[22m[2m │ gzip:   5.44 kB[22m
[2mdist/[22m[36massets/js/SichuanQCDemo-Trx7-2CR.js                                       [39m[1m[2m   17.02 kB[22m[1m[22m[2m │ gzip:   6.48 kB[22m
[2mdist/[22m[36massets/js/EditMedicalRecord-CVwu_GKh.js                                   [39m[1m[2m   17.19 kB[22m[1m[22m[2m │ gzip:   5.50 kB[22m
[2mdist/[22m[36massets/js/DrgGrouperView-BD9jByMG.js                                      [39m[1m[2m   17.25 kB[22m[1m[22m[2m │ gzip:   5.25 kB[22m
[2mdist/[22m[36massets/js/Analysis-Cl79l3L6.js                                            [39m[1m[2m   17.55 kB[22m[1m[22m[2m │ gzip:   6.56 kB[22m
[2mdist/[22m[36massets/js/QCReviewDrawer-DHhPNZaI.js                                      [39m[1m[2m   18.06 kB[22m[1m[22m[2m │ gzip:   6.16 kB[22m
[2mdist/[22m[36massets/js/MedicalRecordsView-D2wSumzU.js                                  [39m[1m[2m   19.00 kB[22m[1m[22m[2m │ gzip:   6.82 kB[22m
[2mdist/[22m[36massets/js/TestMedicalRecordsView-ZG8yfqZy.js                              [39m[1m[2m   19.68 kB[22m[1m[22m[2m │ gzip:   7.46 kB[22m
[2mdist/[22m[36massets/js/SmartImportSimple-ChWH_tcZ.js                                   [39m[1m[2m   19.93 kB[22m[1m[22m[2m │ gzip:   7.30 kB[22m
[2mdist/[22m[36massets/js/WorkstationV3View-9S0UcmnF.js                                   [39m[1m[2m   20.67 kB[22m[1m[22m[2m │ gzip:   7.19 kB[22m
[2mdist/[22m[36massets/js/AnalyticsView-DSotIwry.js                                       [39m[1m[2m   21.09 kB[22m[1m[22m[2m │ gzip:   7.34 kB[22m
[2mdist/[22m[36massets/js/WorkstationRulesView-yLp6Ab6U.js                                [39m[1m[2m   22.22 kB[22m[1m[22m[2m │ gzip:   6.50 kB[22m
[2mdist/[22m[36massets/js/purify.es-h52jTgpa.js                                           [39m[1m[2m   22.68 kB[22m[1m[22m[2m │ gzip:   8.76 kB[22m
[2mdist/[22m[36massets/js/MedicalRecordDetail-BQqbAVHf.js                                 [39m[1m[2m   22.86 kB[22m[1m[22m[2m │ gzip:   8.54 kB[22m
[2mdist/[22m[36massets/js/AllTasksView-Cuyw4Wbm.js                                        [39m[1m[2m   23.14 kB[22m[1m[22m[2m │ gzip:   7.54 kB[22m
[2mdist/[22m[36massets/js/ApiTestView-DMIM0U3D.js                                         [39m[1m[2m   23.77 kB[22m[1m[22m[2m │ gzip:   6.28 kB[22m
[2mdist/[22m[36massets/js/WorkstationV2View-DwTTsvK2.js                                   [39m[1m[2m   24.10 kB[22m[1m[22m[2m │ gzip:   9.37 kB[22m
[2mdist/[22m[36massets/js/LLMApiConfig-2ZV3MxT7.js                                        [39m[1m[2m   24.12 kB[22m[1m[22m[2m │ gzip:   8.59 kB[22m
[2mdist/[22m[36massets/js/CustomRulesManager-AO5IGIrG.js                                  [39m[1m[2m   24.59 kB[22m[1m[22m[2m │ gzip:   8.19 kB[22m
[2mdist/[22m[36massets/js/drg-BBGC99oD.js                                                 [39m[1m[2m   24.96 kB[22m[1m[22m[2m │ gzip:   7.87 kB[22m
[2mdist/[22m[36massets/js/SichuanQCView-43GO2EEP.js                                       [39m[1m[2m   25.75 kB[22m[1m[22m[2m │ gzip:   7.65 kB[22m
[2mdist/[22m[36massets/js/AIProfileDashboard-qO9AvXi1.js                                  [39m[1m[2m   26.30 kB[22m[1m[22m[2m │ gzip:   8.38 kB[22m
[2mdist/[22m[36massets/js/CodingRulesTab-J71waBuU.js                                      [39m[1m[2m   28.66 kB[22m[1m[22m[2m │ gzip:   9.20 kB[22m
[2mdist/[22m[36massets/js/ProfileView-D1PAKzOn.js                                         [39m[1m[2m   28.85 kB[22m[1m[22m[2m │ gzip:   9.06 kB[22m
[2mdist/[22m[36massets/js/DRGGroupingTab.vue_vue_type_script_setup_true_lang-D2s-Fx48.js  [39m[1m[2m   28.96 kB[22m[1m[22m[2m │ gzip:   9.59 kB[22m
[2mdist/[22m[36massets/js/DashboardView-BLEuY5tk.js                                       [39m[1m[2m   30.11 kB[22m[1m[22m[2m │ gzip:  10.06 kB[22m
[2mdist/[22m[36massets/js/RunningRecordsViewNew-DVGbbgrx.js                               [39m[1m[2m   31.93 kB[22m[1m[22m[2m │ gzip:   9.97 kB[22m
[2mdist/[22m[36massets/js/SemanticRulesView-BNmPb043.js                                   [39m[1m[2m   34.30 kB[22m[1m[22m[2m │ gzip:  10.71 kB[22m
[2mdist/[22m[36massets/js/LLMQCDemoEnhancedNew-Bwf-DGHN.js                                [39m[1m[2m   34.67 kB[22m[1m[22m[2m │ gzip:  11.42 kB[22m
[2mdist/[22m[36massets/js/LLMQCDemo-Dd2Vbb9d.js                                           [39m[1m[2m   34.69 kB[22m[1m[22m[2m │ gzip:  12.18 kB[22m
[2mdist/[22m[36massets/js/integrated-qc-engine-DFVTB6Ql.js                                [39m[1m[2m   36.28 kB[22m[1m[22m[2m │ gzip:  11.43 kB[22m
[2mdist/[22m[36massets/js/FeeMonitoring-Br2_VFI7.js                                       [39m[1m[2m   36.62 kB[22m[1m[22m[2m │ gzip:  12.26 kB[22m
[2mdist/[22m[36massets/js/index-T70AYnHr.js                                               [39m[1m[2m   37.76 kB[22m[1m[22m[2m │ gzip:  15.00 kB[22m
[2mdist/[22m[36massets/js/LX33DemoView-Bclczush.js                                        [39m[1m[2m   37.83 kB[22m[1m[22m[2m │ gzip:  12.77 kB[22m
[2mdist/[22m[36massets/js/index-CjWOV9On.js                                               [39m[1m[2m   39.23 kB[22m[1m[22m[2m │ gzip:  10.00 kB[22m
[2mdist/[22m[36massets/js/SettingsView-B6nWMimu.js                                        [39m[1m[2m   49.74 kB[22m[1m[22m[2m │ gzip:  14.75 kB[22m
[2mdist/[22m[36massets/js/DataSyncConfigPage-B_JO5-1l.js                                  [39m[1m[2m   66.14 kB[22m[1m[22m[2m │ gzip:  17.74 kB[22m
[2mdist/[22m[36massets/js/QCAnalysisDemoPanel-ieWQAxu7.js                                 [39m[1m[2m   67.90 kB[22m[1m[22m[2m │ gzip:  21.77 kB[22m
[2mdist/[22m[36massets/js/LLMQCDemoEnhanced-DiyKk9SG.js                                   [39m[1m[2m   68.00 kB[22m[1m[22m[2m │ gzip:  22.41 kB[22m
[2mdist/[22m[36massets/js/useMedicalTextExtraction-RkuIA_0e.js                            [39m[1m[2m   69.00 kB[22m[1m[22m[2m │ gzip:  16.77 kB[22m
[2mdist/[22m[36massets/js/CnDrgGrouperView-k4gI8wzB.js                                    [39m[1m[2m   73.42 kB[22m[1m[22m[2m │ gzip:  17.47 kB[22m
[2mdist/[22m[36massets/js/SettlementForm-D-9k8voS.js                                      [39m[1m[2m   78.03 kB[22m[1m[22m[2m │ gzip:  15.92 kB[22m
[2mdist/[22m[36massets/js/ClinicalWorkstationDemoView-cufLWcNU.js                         [39m[1m[2m   81.05 kB[22m[1m[22m[2m │ gzip:  26.61 kB[22m
[2mdist/[22m[36massets/js/BatchRuleTest-CRNhnaJo.js                                       [39m[1m[2m   86.10 kB[22m[1m[22m[2m │ gzip:  27.80 kB[22m
[2mdist/[22m[36massets/js/customRuleCases-B0Cx4b7B.js                                     [39m[1m[2m   94.72 kB[22m[1m[22m[2m │ gzip:  29.93 kB[22m
[2mdist/[22m[36massets/js/vendor-core-BTH360wJ.js                                         [39m[1m[2m  108.69 kB[22m[1m[22m[2m │ gzip:  42.68 kB[22m
[2mdist/[22m[36massets/js/RulesView-CQOfaB9v.js                                           [39m[1m[2m  117.60 kB[22m[1m[22m[2m │ gzip:  35.28 kB[22m
[2mdist/[22m[36massets/js/PreAnalysisView-BMJyq53_.js                                     [39m[1m[2m  122.05 kB[22m[1m[22m[2m │ gzip:  38.02 kB[22m
[2mdist/[22m[36massets/js/llmServiceNew-CPFEITyX.js                                       [39m[1m[2m  122.81 kB[22m[1m[22m[2m │ gzip:  45.16 kB[22m
[2mdist/[22m[36massets/js/MedicalRecordDetail.legacy-B0a68soo.js                          [39m[1m[2m  129.79 kB[22m[1m[22m[2m │ gzip:  39.72 kB[22m
[2mdist/[22m[36massets/js/index.es-onWy-A_n.js                                            [39m[1m[2m  159.36 kB[22m[1m[22m[2m │ gzip:  53.28 kB[22m
[2mdist/[22m[36massets/js/supabase-DJzva23j.js                                            [39m[1m[2m  176.09 kB[22m[1m[22m[2m │ gzip:  45.44 kB[22m
[2mdist/[22m[36massets/js/WorkstationV4View-C2Ov2FQh.js                                   [39m[1m[2m  214.62 kB[22m[1m[22m[2m │ gzip:  64.38 kB[22m
[2mdist/[22m[36massets/js/FrontPageDemoView-CJ5oS28A.js                                   [39m[1m[2m  379.29 kB[22m[1m[22m[2m │ gzip:  67.91 kB[22m
[2mdist/[22m[36massets/js/qcRuleCases-CGk3CN8O.js                                         [39m[1m[2m  412.67 kB[22m[1m[22m[2m │ gzip: 115.45 kB[22m
[2mdist/[22m[36massets/js/custom_rules_33-CvfnpkCn.js                                     [39m[1m[33m  518.34 kB[39m[22m[2m │ gzip:  89.27 kB[22m
[2mdist/[22m[36massets/js/SmartImportMedicalRecord-BZGhD7CL.js                            [39m[1m[33m  542.49 kB[39m[22m[2m │ gzip: 144.93 kB[22m
[2mdist/[22m[36massets/js/vendor-echarts-BuKaPK29.js                                      [39m[1m[33m1,041.47 kB[39m[22m[2m │ gzip: 345.75 kB[22m
[2mdist/[22m[36massets/js/vendor-export-Bb_uRUdk.js                                       [39m[1m[33m1,057.49 kB[39m[22m[2m │ gzip: 329.44 kB[22m
[2mdist/[22m[36massets/js/vendor-antd-_4dukHEv.js                                         [39m[1m[33m1,365.69 kB[39m[22m[2m │ gzip: 391.95 kB[22m
[2mdist/[22m[36massets/js/grouper-engines-CbA1ubM8.js                                     [39m[1m[33m4,037.57 kB[39m[22m[2m │ gzip: 651.38 kB[22m
[32m✓ built in 40.17s[39m
[unplugin-vue-components] component "QCAnalysisPanel"(D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/src/components/medical/QCAnalysisPanel.vue) has naming conflicts with other components, ignored.
[unplugin-vue-components] component "NotificationCenter"(D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/src/components/notification/NotificationCenter.vue) has naming conflicts with other components, ignored.
Browserslist: browsers data (caniuse-lite) is 6 months old. Please run:
  npx update-browserslist-db@latest
  Why you should do it regularly: https://github.com/browserslist/update-db#readme
[33m
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.[39m
```
- backend_release_gate_runner: PASS (37.46s)
```text
[backend-gate] START auth_guard: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe scripts/check_auth_guard.py
[backend-gate] END   auth_guard: PASS (0.07s)
[backend-gate] START secret_hygiene: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe scripts/check_secret_hygiene.py
[backend-gate] END   secret_hygiene: PASS (0.08s)
[backend-gate] START migration_roundtrip: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe scripts/check_migration_roundtrip.py
[backend-gate] END   migration_roundtrip: PASS (3.85s)
[backend-gate] START pytest_contract: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe -m pytest -q tests/unit/test_auth_sync_contract.py tests/unit/test_sync_router.py
[backend-gate] END   pytest_contract: PASS (16.98s)
[backend-gate] START pytest_security_consistency: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe -m pytest -q tests/unit/test_security_hardening.py tests/unit/test_sync_consistency.py tests/unit/test_system_api.py
[backend-gate] END   pytest_security_consistency: PASS (9.21s)
[backend-gate] START pytest_integration_smoke: C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe -m pytest -q tests/integration/test_release_gate_smoke.py
[backend-gate] END   pytest_integration_smoke: PASS (7.13s)
Backend release gates passed.
```