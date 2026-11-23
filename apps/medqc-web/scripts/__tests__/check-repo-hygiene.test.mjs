import assert from 'node:assert/strict'
import { test } from 'node:test'
import { analyzeDiff } from '../check-repo-hygiene.mjs'

const web = 'apps/medqc-web/'
const src = `${web}src/`
const workstation = `${src}views/workstation-v4/`

function analyze(addedFiles, changes = {}) {
  const addedLinesByFile = new Map(Object.entries(changes).map(([file, lines]) => [
    file,
    lines.map((line, index) => typeof line === 'string' ? { lineNumber: index + 1, text: line } : line),
  ]))
  return analyzeDiff({ addedFiles, addedLinesByFile })
}

test('只拦截直接加在三处根目录的临时文件和报告', () => {
  const blocked = [
    'scratch.py', 'scratch.js', 'scratch.sh', 'scratch.ps1', 'scratch.csv',
    'scratch.xlsx', 'scratch.txt', 'scratch.log', 'scratch.html', 'scratch.pdf',
    `${web}AUDIT_REPORT.md`, `${web}backend/DAILY_SUMMARY.md`,
  ]
  const allowed = [
    'eslint.config.js', 'dev-env.sh', `${web}vite.config.mjs`, `${web}index.html`,
    `${web}backend/requirements.txt`, `${web}backend/requirements-dev.txt`,
    `${web}backend/scripts/rebuild.py`, `${web}backend/README.md`, 'other/scratch.py',
  ]
  assert.deepEqual(analyze([...blocked, ...allowed], { 'historical.py': ['print("changed")'] })
    .map(({ file }) => file), blocked)
})

test('仅在 medqc-web 下拦截新加的日志、临时文件和 Vue 镜像', () => {
  const blocked = [
    `${web}.logs-dev.txt`, `${web}tools/.tmp-probe/output.json`,
    `${src}components/Old.legacy.vue`, `${src}components/Mirror.vue.ts`,
  ]
  const allowed = ['other/.tmp-probe', `${web}tools/logs-dev.txt`, `${src}components/New.vue`, `${src}types.ts`]
  assert.deepEqual(analyze([...blocked, ...allowed], { [`${web}.logs-old.txt`]: ['updated'] })
    .map(({ file }) => file), blocked)
})

test('在工作台和新样式文件的新增行拦截硬编码颜色和旧变量', () => {
  const existing = `${workstation}Overview.vue`
  const newVue = `${src}views/New.vue`
  const newCss = `${src}styles/new.css`
  const newScss = `${src}styles/new.scss`
  const violations = analyze([newVue, newCss, newScss], {
    [existing]: ['.row { color: #abc; }', 'gap: var(--workstation-gap);', 'border: 1px solid #12345678;'],
    [newVue]: ['<div style="background: #abcd">', `<div :style="{ color: '#123456' }">`],
    [newCss]: ['.accent { color: #abcdef; }'],
    [newScss]: ['$accent: #abcdef;'],
  })
  assert.deepEqual(violations.map(({ file, lineNumber }) => [file, lineNumber]), [
    [existing, 1], [existing, 2], [existing, 3], [newVue, 1], [newVue, 2], [newCss, 1], [newScss, 1],
  ])
})

test('样式规则允许 token、实体、链接、SVG 引用、选择器及范围外文件', () => {
  const testFile = `${workstation}__tests__/Fixture.vue`
  const newCss = `${src}styles/new.css`
  assert.deepEqual(analyze([newCss, testFile, `${src}snapshot.ts`], {
    [`${workstation}Overview.vue`]: [
      '<a href="#abc">&#123; &#xabc;</a>', '<div>{{ label }} #abc</div>',
      'color: var(--mq-text);', `<div style="filter: url('#abc');">`,
      'mask: url(#abc);', 'content: "&#xabc;";',
    ],
    [newCss]: ['a:hover #abc {', '#abcdef { display: grid; }'],
    [testFile]: ['color: #fff;'],
    [`${src}snapshot.ts`]: ['color: #fff;'],
    [`${src}styles/existing.css`]: ['color: #fff;'],
  }), [])
})

test('只在业务源码的新增行拦截原生确认与日期控件', () => {
  const file = `${src}views/Panel.vue`
  const violations = analyze([], {
    [file]: [
      'Modal.confirm({ title });', 'window.confirm(question);', '<input name="start" type="date">',
      '<input', "  type='date'>", '<DatePicker />', '<input type="datetime-local">', 'service.confirm(question);',
      `<input data-hint=' type="date" '>`,
    ],
    [`${src}views/Panel.spec.ts`]: ['Modal.confirm({});'],
    [`${src}views/Panel.test.ts`]: ['window.confirm(question);'],
    [`${src}views/__tests__/Fixture.vue`]: ['<input type="date">'],
    [`${web}scripts/fixture.js`]: ['window.confirm(question);'],
  })
  assert.deepEqual(violations.map(({ file, lineNumber }) => [file, lineNumber]), [
    [file, 1], [file, 2], [file, 3], [file, 5],
  ])
})

test('拦截病例三键手拼和时间格式化定义，同时排除权威模块', () => {
  const file = `${src}utils/new.ts`
  const violations = analyze([], {
    [file]: [
      'JSON.stringify([instituteId, patientId, visitId])',
      'JSON.stringify([', '  record.institute, record.patient, record.visit,', '])',
      'function formatDate(value) {}', 'const formatDateTime = (value) => value',
      'const key = JSON.stringify([instituteId, visitId])', 'formatDateTime(value)',
      'function formatDateRange(value) {}', 'const formatDateTimeLabel = formatDateTime(value)',
    ],
    [`${src}utils/caseRecordKey.ts`]: ['JSON.stringify([instituteId, patientId, visitId])'],
    [`${src}utils/qcTaskTime.ts`]: ['const formatDateTime = (value) => value'],
    [`${src}utils/clinicalTime.ts`]: ['function formatDate(value) {}'],
    [`${src}utils/new.test.ts`]: ['function formatDate(value) {}'],
  })
  assert.deepEqual(violations.map(({ file, lineNumber }) => [file, lineNumber]), [
    [file, 1], [file, 2], [file, 5], [file, 6],
  ])
})

test('不把不连续的新增行拼接为同一处违规', () => {
  assert.deepEqual(analyze([], {
    [`${src}views/Panel.vue`]: [
      { lineNumber: 1, text: '<input' }, { lineNumber: 3, text: 'type="date">' },
      { lineNumber: 5, text: 'JSON.stringify([' },
      { lineNumber: 9, text: 'instituteId, patientId, visitId])' },
    ],
  }), [])
})

test('仅接受带理由的单行注释豁免', () => {
  const file = `${workstation}Panel.vue`
  const violations = analyze(['scratch.sh'], {
    'scratch.sh': ['# hygiene-ignore: 与本机开发工具兼容'],
    [file]: [
      'color: #fff; /* hygiene-ignore: 第三方嵌入组件的要求 */',
      '<input type="date"> <!-- hygiene-ignore: 浏览器兼容测试入口 -->',
      'window.confirm(question); // hygiene-ignore: 暂时兼容宿主',
      'Modal.confirm({}); // hygiene-ignore:   ',
      'window.confirm("hygiene-ignore: 这是文案");',
      'color: #fff; /* hygiene-ignore: */',
      'window.confirm("// hygiene-ignore: 这也是文案");',
    ],
  })
  assert.deepEqual(violations.map(({ file, lineNumber }) => [file, lineNumber]), [
    [file, 4], [file, 5], [file, 6], [file, 7],
  ])
})
