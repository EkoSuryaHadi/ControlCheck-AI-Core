export const PUBLIC_BETA_MAX_UPLOAD_BYTES: number
export const ASYNC_UPLOAD_MAX_BYTES: number

export function validatePublicBetaUpload(file: {
  name: string
  size: number
}): string | null

export function shouldUseAsyncUpload(file: { size: number }): boolean
