# Workstation V4 测试文档目录

本目录只覆盖 `workstation v4` 正式功能，不包含 `demo/test/debug` 页面。

关联文档：

- [workstation*v4*项目非CDM数据结构CSV说明.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/workstation_v4_项目非CDM数据结构CSV说明.md)
- [project_pg_field_list_non_cdm_workstation_v4.csv](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/project_pg_field_list_non_cdm_workstation_v4.csv)
- [cdm_field_list.csv](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/docs/cdm_field_list.csv)
- [PRD-病案工作台V4.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/PRD-病案工作台V4.md)

目录说明：

- [自动化测试清单.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/自动化测试清单.md)
  说明哪些能力适合自动化、自动化边界是什么、上线前自动化闸门是什么。
- [必须人工测试清单.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/必须人工测试清单.md)
  说明哪些场景不能只靠脚本放行，必须由业务或测试人员人工确认。
- [自动化测试实施清单.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/自动化测试实施清单.md)
  给出自动化落地顺序、前置数据、断言点、建议命令和关键落库表。
- [自动化测试执行表.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/自动化测试执行表.md)
  按页面路径列出测试动作、关键接口、对应数据表、预期返回和自动化方式。

建议执行顺序：

1. 先按 [自动化测试实施清单.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/自动化测试实施清单.md) 建立最小自动化闸门。
2. 跑完自动化后，再按 [必须人工测试清单.md](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/workstation-v4/必须人工测试清单.md) 做业务验收。
3. 放行前同时满足自动化全绿和人工主链路全通过。
