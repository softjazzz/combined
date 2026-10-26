import type { RouteLocationRaw } from 'vue-router'
import type { ComputedRef, InjectionKey } from 'vue'
import type { DoctorInteractionTarget } from '@/views/workstation-v4/types'

export const MESSAGE_CENTER_PATH = '/workstation-v5/messages'
export const MESSAGE_CENTER_ROLES = ['admin', 'qc_manager', 'qc_staff', 'sync_admin', 'super_admin']
export const WORKSTATION_REMINDER_PANEL: InjectionKey<ComputedRef<boolean>> = Symbol(
  'workstation-reminder-panel',
)

export function canUseReminderPanel(roles: readonly string[]) {
  return !roles.some((role) => ['admin', 'sync_admin', 'super_admin'].includes(role))
}

export function canUseMessageCenter(roles: string[]) {
  return roles.some((role) => MESSAGE_CENTER_ROLES.includes(role))
}

export function notificationLocation(target: DoctorInteractionTarget): RouteLocationRaw {
  switch (target.kind) {
    case 'qc_result_ready':
      return { path: '/workstation-v5/qc-result', query: { notification_id: target.id } }
    case 'account_registration':
      return {
        path: '/workstation-v5/system-config',
        query: { tab: 'accounts', registration_id: target.id },
      }
    case 'account_registration_result':
      return { path: '/auth/register', query: { mode: 'status' } }
    case 'case_communication':
      return { path: '/workstation-v5/case-communications', query: { communication_id: target.id } }
    case 'rectification':
      return { path: '/workstation-v5/feedback', query: { rectification_id: target.id } }
    case 'modern_appeal':
      return { path: '/workstation-v5/feedback', query: { appeal_id: target.id } }
  }
}
