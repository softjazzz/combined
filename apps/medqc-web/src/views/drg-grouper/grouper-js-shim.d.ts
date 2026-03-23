declare module './sichuan2024Grouper' {
  export const CC: Record<string, string>
  export const CCE: Record<string, string>
  export const MCC: Record<string, string>
  export const SS_VALID: string[]
  export function group_record(input: Record<string, unknown>): Record<string, unknown>
}

declare module './cnDrg2023Grouper' {
  export const CC: Record<string, string>
  export const CCE: Record<string, string>
  export const MCC: Record<string, string>
  export const SS_VALID: string[]
  export function group_record(input: Record<string, unknown>): Record<string, unknown>
}
