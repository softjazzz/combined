import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type ProductActivationState =
  'not_required' | 'missing' | 'active' | 'expired' | 'invalid' | 'not_configured'

export interface ProductActivationStatus {
  status: ProductActivationState
  required: boolean
  version?: string
  product?: string
  customer?: string
  edition?: string
  serial?: string
  issued_at?: string
  expires_at?: string
  activated_at?: string
}

export interface ProductActivationApiResult<T> {
  success: boolean
  data?: T
  message?: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeStatus(value: unknown): ProductActivationStatus {
  const source = isRecord(value) ? value : {}
  const status = source.status
  const validStates: ProductActivationState[] = [
    'not_required',
    'missing',
    'active',
    'expired',
    'invalid',
    'not_configured',
  ]
  return {
    status: validStates.includes(status as ProductActivationState)
      ? (status as ProductActivationState)
      : 'invalid',
    required: source.required === true,
    version: typeof source.version === 'string' ? source.version : undefined,
    product: typeof source.product === 'string' ? source.product : undefined,
    customer: typeof source.customer === 'string' ? source.customer : undefined,
    edition: typeof source.edition === 'string' ? source.edition : undefined,
    serial: typeof source.serial === 'string' ? source.serial : undefined,
    issued_at: typeof source.issued_at === 'string' ? source.issued_at : undefined,
    expires_at: typeof source.expires_at === 'string' ? source.expires_at : undefined,
    activated_at: typeof source.activated_at === 'string' ? source.activated_at : undefined,
  }
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallbackMessage: string,
): Promise<ProductActivationApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return { success: normalized.success, data: normalized.data, message: normalized.message }
  } catch (error: unknown) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, fallbackMessage),
    }
  }
}

export async function getProductActivationStatus(): Promise<
  ProductActivationApiResult<ProductActivationStatus>
> {
  const result = await request<unknown>(
    { method: 'GET', url: '/api/v1/product-activation/status' },
    '获取产品激活状态失败',
  )
  return result.success
    ? { ...result, data: normalizeStatus(result.data) }
    : (result as ProductActivationApiResult<ProductActivationStatus>)
}

export async function activateProduct(
  activationCode: string,
): Promise<ProductActivationApiResult<ProductActivationStatus>> {
  const result = await request<unknown>(
    {
      method: 'POST',
      url: '/api/v1/product-activation/activate',
      data: { activation_code: activationCode },
    },
    '激活产品失败',
  )
  return result.success
    ? { ...result, data: normalizeStatus(result.data) }
    : (result as ProductActivationApiResult<ProductActivationStatus>)
}
