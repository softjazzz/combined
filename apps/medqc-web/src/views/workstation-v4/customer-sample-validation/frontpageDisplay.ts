import type { FrontpageDisplay, FrontpageDisplayTable } from './types'

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function scalar(value: unknown): string | null {
  if (typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'boolean') {
    return null
  }
  return String(value).trim() || null
}

function table(value: unknown): FrontpageDisplayTable {
  const source = object(value)
  const columns = list(source.columns)
    .map((entry) => object(entry))
    .map((entry) => ({ key: scalar(entry.key) || '', label: scalar(entry.label) || '' }))
    .filter((entry) => Boolean(entry.key && entry.label))
  return {
    columns,
    rows: list(source.rows).map((row) =>
      Object.fromEntries(columns.map(({ key }) => [key, scalar(object(row)[key])])),
    ),
  }
}

export function normalizeFrontpageDisplay(value: unknown): FrontpageDisplay | undefined {
  const source = object(value)
  if (!Array.isArray(source.groups)) return undefined
  return {
    groups: source.groups
      .map((entry) => {
        const group = object(entry)
        return {
          key: scalar(group.key) || '',
          label: scalar(group.label) || '首页信息',
          fields: list(group.fields)
            .map((item) => {
              const field = object(item)
              return {
                key: scalar(field.key) || '',
                label: scalar(field.label) || '首页字段',
                value: scalar(field.value),
              }
            })
            .filter((field) => Boolean(field.key)),
        }
      })
      .filter((group) => Boolean(group.key)),
    diagnoses: table(source.diagnoses),
    surgeries: table(source.surgeries),
  }
}

/** 只做字段对接，复用系统首页表单；不生成诊断或补写源值。 */
export function toSystemFrontpageSheet(display: FrontpageDisplay) {
  const fields = (cost: boolean) =>
    Object.fromEntries(
      display.groups
        .filter((group) => (group.key === 'cost') === cost)
        .flatMap((group) => group.fields.map((field) => [field.key, field.value])),
    )
  return {
    basic: fields(false),
    cost: fields(true),
    diagnoses: display.diagnoses.rows.map((row) => ({ ...row })),
    surgeries: display.surgeries.rows.map((row) => ({
      ...row,
      surgeon_code: row.surgeon_physician_code ?? null,
    })),
  }
}
